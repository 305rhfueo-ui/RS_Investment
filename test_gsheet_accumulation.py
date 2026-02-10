
import gsheet_handler

# Dummy Data
test_data = [
    {
        'Ticker': 'TEST_A',
        'CY_Est': 10.0, 'CY_30': 9.0,
        'NY_Est': 12.0, 'NY_30': 11.0,
        'CY_Trend': 11.11, 'NY_Trend': 9.09,
        'Up_Count': 5, 'Down_Count': 2, 'Up_Down_Ratio': 71.43
    },
    {
        'Ticker': 'TEST_B',
        'CY_Est': 5.0, 'CY_30': 5.0,
        'NY_Est': 6.0, 'NY_30': 6.0,
        'CY_Trend': 0.0, 'NY_Trend': 0.0,
        'Up_Count': 0, 'Down_Count': 0, 'Up_Down_Ratio': 0.0
    }
]

print("Testing Google Sheet Accumulation (RS_Estimate)...")
gsheet_handler.update_sheet(test_data)
print("Test Complete. Check the 'RS_Estimate' tab.")
