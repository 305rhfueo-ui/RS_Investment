
import gsheet_handler

# Dummy Data
test_data = [
    {
        'Ticker': 'TEST_A',
        'CY_Est': 10.0, 'CY_30': 9.0,
        'NY_Est': 12.0, 'NY_30': 11.0
    },
    {
        'Ticker': 'TEST_B',
        'CY_Est': 5.0, 'CY_30': 5.0, # No change expected if repeated
        'NY_Est': 6.0, 'NY_30': 6.0
    }
]

print("Testing Google Sheet Accumulation...")
gsheet_handler.update_sheet(test_data)
print("Test Complete. Check the 'Accumulated_Data' tab.")
