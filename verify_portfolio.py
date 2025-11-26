from portfolio_manager import load_portfolio, save_portfolio, get_default_portfolio
import os
import json

TEST_FILE = "portfolio.json"

def test_persistence():
    print("Testing Portfolio Persistence...")
    
    # 1. Clean up existing file
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)
        
    # 2. Test Default Load
    weights = load_portfolio()
    default_weights = get_default_portfolio()
    assert weights == default_weights, "Failed to load default weights"
    print("✓ Default load successful")
    
    # 3. Test Save
    new_weights = {"AAPL": 0.5, "GOOG": 0.5}
    save_success = save_portfolio(new_weights)
    assert save_success, "Failed to save portfolio"
    assert os.path.exists(TEST_FILE), "File not created"
    print("✓ Save successful")
    
    # 4. Test Load Saved
    loaded_weights = load_portfolio()
    assert loaded_weights == new_weights, "Failed to load saved weights"
    print("✓ Load saved successful")
    
    # 5. Cleanup
    os.remove(TEST_FILE)
    print("✓ Cleanup successful")
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_persistence()
