
import gsheet_handler

# Dummy Data
# Dummy Data
test_data = [
    {
        'Ticker': 'TEST_A',
        'CY_Current': 39.45, 'CY_30Ago': 13.29, 'CY_Trend': 196.83,
        'NY_Current': 76.34, 'NY_30Ago': 22.17, 'NY_Trend': 244.33,
        'Up_Count': 4, 'Down_Count': 0, 'Up_Down_Ratio': 100.0,
        'Target_Status': 'YES'
    },
    {
        'Ticker': 'TEST_B',
        'CY_Current': 5.0, 'CY_30Ago': 5.0, 'CY_Trend': 0.0,
        'NY_Current': 6.0, 'NY_30Ago': 6.0, 'NY_Trend': 0.0,
        'Up_Count': 0, 'Down_Count': 0, 'Up_Down_Ratio': 0.0,
        'Target_Status': 'NO'
    }
]

print("Testing Google Sheet Accumulation (RS_Estimate)...")
gsheet_handler.update_sheet(test_data)
print("Test Complete. Check the 'RS_Estimate' tab.")
