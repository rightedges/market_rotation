def test_redistribution(base_weights, benchmark_ticker, override_weight):
    print(f"Original: {base_weights}")
    print(f"Override {benchmark_ticker} to {override_weight}")
    
    base_weights = base_weights.copy()
    base_weights[benchmark_ticker] = override_weight
    remaining_target = 1.0 - override_weight
    
    other_tickers = [t for t in base_weights if t != benchmark_ticker]
    current_other_sum = sum(base_weights[t] for t in other_tickers)
    
    if current_other_sum > 0:
        for t in other_tickers:
            base_weights[t] = (base_weights[t] / current_other_sum) * remaining_target
    elif other_tickers:
         equal_weight = remaining_target / len(other_tickers)
         for t in other_tickers:
             base_weights[t] = equal_weight
             
    print(f"New: {base_weights}")
    print(f"Sum: {sum(base_weights.values())}")
    print("-" * 20)

# Test Case 1: Standard
test_redistribution({'VOO': 0.4, 'SPMO': 0.2, 'QQQ': 0.2, 'BRK-B': 0.2}, 'VOO', 0.5)

# Test Case 2: Reduce benchmark
test_redistribution({'VOO': 0.4, 'SPMO': 0.2, 'QQQ': 0.2, 'BRK-B': 0.2}, 'VOO', 0.1)

# Test Case 3: Zero sum others
test_redistribution({'VOO': 1.0, 'SPMO': 0.0}, 'VOO', 0.5)
