from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Portfolio, Holding
from app.services.market_data import check_symbol, get_prices

bp = Blueprint('portfolio', __name__, url_prefix='/portfolio')

@bp.route('/')
@login_required
def index():
    portfolios = current_user.portfolios.all()
    return render_template('portfolio/index.html', portfolios=portfolios)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form['name']
        type = request.form['type']
        portfolio = Portfolio(name=name, type=type, owner=current_user)
        db.session.add(portfolio)
        db.session.commit()
        flash('Portfolio created successfully!')
        return redirect(url_for('portfolio.index'))
    return render_template('portfolio/create.html')

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

