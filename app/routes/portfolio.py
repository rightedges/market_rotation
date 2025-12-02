from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, Response, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Portfolio, Holding
from app.services.market_data import check_symbol, get_prices
import json
from datetime import datetime
import io

bp = Blueprint('portfolio', __name__, url_prefix='/portfolio')

@bp.route('/')
@login_required
def index():
    portfolios = current_user.portfolios.all()
    return render_template('portfolio/index.html', portfolios=portfolios)

def check_portfolio_exists(name, type, user_id, exclude_id=None):
    query = Portfolio.query.filter_by(name=name, type=type, user_id=user_id)
    if exclude_id:
        query = query.filter(Portfolio.id != exclude_id)
    return query.first() is not None

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form['name']
        type = request.form['type']
        
        if check_portfolio_exists(name, type, current_user.id):
            flash(f'A portfolio named "{name}" with type "{type}" already exists.')
            return redirect(url_for('portfolio.create'))
            
        portfolio = Portfolio(name=name, type=type, owner=current_user)
        db.session.add(portfolio)
        db.session.commit()
        flash('Portfolio created successfully!')
        return redirect(url_for('portfolio.index'))
    return render_template('portfolio/create.html')

@bp.route('/create_example')
@login_required
def create_example():
    # Create example portfolio
    portfolio = Portfolio(name='Example Portfolio (Test)', type='RRSP', owner=current_user)
    db.session.add(portfolio)
    
    # Add holdings (25% each)
    holdings_data = [
        ('VOO', 10, 25.0),
        ('QQQ', 10, 25.0),
        ('BRK-B', 10, 25.0),
        ('SPMO', 10, 25.0)
    ]
    
    for symbol, units, target in holdings_data:
        holding = Holding(symbol=symbol, units=units, target_percentage=target, portfolio=portfolio)
        db.session.add(holding)
        
    db.session.commit()
    flash('Example portfolio created! Feel free to test the features and delete it later.')
    return redirect(url_for('portfolio.index'))

@bp.route('/<int:id>')
@login_required
def view(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
    
    holdings = portfolio.holdings.all()
    symbols = [h.symbol for h in holdings]
    prices = get_prices(symbols)
    
    # Calculate total value and distribution
    total_value = 0
    holdings_data = []
    
    for h in holdings:
        price_data = prices.get(h.symbol)
        
        if price_data:
            # API returned data, update cache
            price = price_data['price']
            timestamp = price_data['timestamp']
            h.last_price = price
            h.last_price_timestamp = timestamp
        else:
            # API failed, use cache
            price = h.last_price if h.last_price is not None else 0
            timestamp = h.last_price_timestamp if h.last_price_timestamp else "N/A"
            
        value = price * h.units
        total_value += value
        holdings_data.append({
            'id': h.id,
            'symbol': h.symbol,
            'units': h.units,
            'price': price,
            'timestamp': timestamp,
            'value': value
        })
        
    db.session.commit() # Save updated prices to DB
        
    return render_template('portfolio/view.html', portfolio=portfolio, holdings=holdings_data, total_value=total_value)

@bp.route('/<int:id>/add_stock', methods=['GET', 'POST'])
@login_required
def add_stock(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    if request.method == 'POST':
        symbol = request.form['symbol'].upper()
        units = float(request.form['units'])
        
        if not check_symbol(symbol):
            flash(f'Invalid symbol: {symbol}. Please check if it exists on Twelve Data.')
            return redirect(url_for('portfolio.add_stock', id=id))
            
        holding = Holding(symbol=symbol, units=units, portfolio=portfolio)
        db.session.add(holding)
        db.session.commit()
        flash(f'Added {symbol} to portfolio.')
        return redirect(url_for('portfolio.view', id=id))
        
    return render_template('portfolio/add_stock.html', portfolio=portfolio)

@bp.route('/edit_stock/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_stock(id):
    holding = Holding.query.get_or_404(id)
    if holding.portfolio.owner != current_user:
        abort(403)
        
    if request.method == 'POST':
        units = float(request.form['units'])
        holding.units = units
        db.session.commit()
        flash(f'Updated {holding.symbol} units.')
        return redirect(url_for('portfolio.view', id=holding.portfolio.id))
        
    return render_template('portfolio/edit_stock.html', holding=holding)

@bp.route('/delete_stock/<int:id>')
@login_required
def delete_stock(id):
    holding = Holding.query.get_or_404(id)
    if holding.portfolio.owner != current_user:
        abort(403)
    
    portfolio_id = holding.portfolio.id
    db.session.delete(holding)
    db.session.commit()
    flash('Stock removed from portfolio.')
    return redirect(url_for('portfolio.view', id=portfolio_id))

@bp.route('/delete/<int:id>')
@login_required
def delete(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    db.session.delete(portfolio)
    db.session.commit()
    flash('Portfolio deleted successfully.')
    return redirect(url_for('portfolio.index'))

@bp.route('/rename/<int:id>', methods=['GET', 'POST'])
@login_required
def rename(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    if request.method == 'POST':
        new_name = request.form['name']
        new_type = request.form['type']
        
        if check_portfolio_exists(new_name, new_type, current_user.id, exclude_id=id):
            flash(f'A portfolio named "{new_name}" with type "{new_type}" already exists.')
            return redirect(url_for('portfolio.rename', id=id))
            
        portfolio.name = new_name
        portfolio.type = new_type
        db.session.commit()
        flash('Portfolio renamed successfully.')
        return redirect(url_for('portfolio.index'))
        
    return render_template('portfolio/rename.html', portfolio=portfolio)

@bp.route('/duplicate/<int:id>')
@login_required
def duplicate(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    # Create new portfolio
    new_name = f"Copy of {portfolio.name}"
    
    if check_portfolio_exists(new_name, portfolio.type, current_user.id):
        flash(f'Cannot duplicate: A portfolio named "{new_name}" already exists.')
        return redirect(url_for('portfolio.index'))

    new_portfolio = Portfolio(
        name=new_name,
        type=portfolio.type,
        owner=current_user,
        analysis_benchmark_weight=portfolio.analysis_benchmark_weight,
        analysis_benchmark_ticker=portfolio.analysis_benchmark_ticker,
        analysis_relaxed_mode=portfolio.analysis_relaxed_mode,
        analysis_trend_weight=portfolio.analysis_trend_weight,
        analysis_relative_strength_weight=portfolio.analysis_relative_strength_weight
    )
    db.session.add(new_portfolio)
    
    # Copy holdings
    for holding in portfolio.holdings:
        new_holding = Holding(
            symbol=holding.symbol,
            units=holding.units,
            target_percentage=holding.target_percentage,
            portfolio=new_portfolio,
            last_price=holding.last_price,
            last_price_timestamp=holding.last_price_timestamp
        )
        db.session.add(new_holding)
        
    db.session.commit()
    flash('Portfolio duplicated successfully.')
    return redirect(url_for('portfolio.index'))
@bp.route('/rebalance/<int:id>', methods=['GET', 'POST'])
@login_required
def rebalance(id):
    portfolio = Portfolio.query.get_or_404(id)
    if portfolio.owner != current_user:
        abort(403)
        
    holdings = portfolio.holdings.all()
    symbols = [h.symbol for h in holdings]
    prices = get_prices(symbols)
    
    # Prepare data for the form
    holdings_data = []
    total_value = 0
    for h in holdings:
        price_data = prices.get(h.symbol)
        
        if price_data:
            # API returned data, update cache
            price = price_data['price']
            h.last_price = price
            # We could update timestamp too but rebalance view doesn't show it usually, 
            # but good to keep consistent.
            h.last_price_timestamp = price_data['timestamp']
        else:
            # API failed, use cache
            price = h.last_price if h.last_price is not None else 0
            
        value = price * h.units
        total_value += value
        holdings_data.append({
            'symbol': h.symbol,
            'units': h.units,
            'price': price,
            'value': value,
            'target_percentage': h.target_percentage
        })
        
    db.session.commit() # Save updated prices
        
    if request.method == 'POST':
        cash = float(request.form.get('cash', 0))
        
        # Parse target ratios (percentages)
        targets = {}
        total_ratio = 0
        for h in holdings:
            percentage = float(request.form.get(f'ratio_{h.symbol}', 0))
            
            # Save the target percentage to the database
            h.target_percentage = percentage
            
            ratio = percentage / 100.0
            targets[h.symbol] = ratio
            total_ratio += ratio
            
        db.session.commit()
            
        # Validate total ratio (should be close to 1.0)
        # We can just proceed; if it doesn't sum to 100%, the user might have intended to leave cash or made a mistake.
        # But the math works regardless (it will just target that % of the total portfolio).

        new_total_value = total_value + cash
        
        # Calculate actions
        actions = []
        for h in holdings:
            target_ratio = targets.get(h.symbol, 0)
            target_value = new_total_value * target_ratio
            # Use cached price if API failed (which we handled above, but we need to access it here)
            # Since we updated the DB objects above, we can use h.last_price
            price = h.last_price if h.last_price is not None else 0
            
            current_value = h.units * price
            diff = target_value - current_value
            
            if price > 0:
                units_to_change = diff / price
                action_type = 'Buy' if units_to_change > 0 else 'Sell'
                actions.append({
                    'symbol': h.symbol,
                    'price': price,
                    'current_units': h.units,
                    'target_value': target_value,
                    'units_to_change': abs(round(units_to_change, 2)),
                    'action': action_type
                })
                
        return render_template('portfolio/rebalance_result.html', portfolio=portfolio, actions=actions, cash=cash, total_value=new_total_value)

    return render_template('portfolio/rebalance.html', portfolio=portfolio, holdings=holdings_data, total_value=total_value)


@bp.route('/export')
@login_required
def export_data():
    portfolios = current_user.portfolios.all()
    data = []
    
    for p in portfolios:
        p_data = {
            'name': p.name,
            'type': p.type,
            'analysis_benchmark_weight': p.analysis_benchmark_weight,
            'analysis_benchmark_ticker': p.analysis_benchmark_ticker,
            'analysis_relaxed_mode': p.analysis_relaxed_mode,
            'analysis_trend_weight': p.analysis_trend_weight,
            'analysis_relative_strength_weight': p.analysis_relative_strength_weight,
            'holdings': []
        }
        
        for h in p.holdings:
            h_data = {
                'symbol': h.symbol,
                'units': h.units,
                'target_percentage': h.target_percentage
            }
            p_data['holdings'].append(h_data)
            
        data.append(p_data)
        
    json_str = json.dumps(data, indent=4)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"market_rotation_export_{timestamp}.json"
    
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@bp.route('/import', methods=['POST'])
@login_required
def import_data():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('portfolio.index'))
        
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('portfolio.index'))
        
    if file:
        try:
            data = json.load(file)
            
            if not isinstance(data, list):
                flash('Invalid file format: Expected a list of portfolios')
                return redirect(url_for('portfolio.index'))
                
            count = 0
            for p_data in data:
                # Handle name conflicts
                name = p_data.get('name', 'Untitled')
                base_name = name
                
                # Check if exists
                existing = Portfolio.query.filter_by(name=name, owner=current_user).first()
                if existing:
                    name = f"{base_name} (Imported)"
                    # Check again
                    if Portfolio.query.filter_by(name=name, owner=current_user).first():
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        name = f"{base_name} (Imported {timestamp})"
                
                portfolio = Portfolio(
                    name=name,
                    type=p_data.get('type', 'General'),
                    owner=current_user,
                    analysis_benchmark_weight=p_data.get('analysis_benchmark_weight'),
                    analysis_benchmark_ticker=p_data.get('analysis_benchmark_ticker'),
                    analysis_relaxed_mode=p_data.get('analysis_relaxed_mode', False),
                    analysis_trend_weight=p_data.get('analysis_trend_weight', 0.10),
                    analysis_relative_strength_weight=p_data.get('analysis_relative_strength_weight', 0.05)
                )
                db.session.add(portfolio)
                
                for h_data in p_data.get('holdings', []):
                    holding = Holding(
                        symbol=h_data['symbol'],
                        units=h_data['units'],
                        target_percentage=h_data.get('target_percentage', 0.0),
                        portfolio=portfolio
                    )
                    db.session.add(holding)
                    
                count += 1
                
            db.session.commit()
            flash(f'Successfully imported {count} portfolios.')
            
        except json.JSONDecodeError:
            flash('Invalid JSON file')
        except Exception as e:
            db.session.rollback()
            flash(f'Error importing data: {str(e)}')
            
    return redirect(url_for('portfolio.index'))
