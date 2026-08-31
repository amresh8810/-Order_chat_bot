// ---------------------------------------------------------
// Paste this code in Google Sheets -> Extensions -> Apps Script
// ---------------------------------------------------------
function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var params = e.parameter;
  
  if (params.type === "feedback") {
    // If feedback rating
    sheet.appendRow([params.order_id, "", "", "", "", "", "", params.rating]);
    return ContentService.createTextOutput("Rating Logged");
  }

  // Log new order
  var orderId = params.order_id || "";
  var date = params.date || "";
  var name = params.name || "";
  var address = params.address || "";
  var phone = params.phone || "";
  var product = params.product || "";
  var price = params.price || "";

  sheet.appendRow([orderId, date, name, address, phone, product, price]);
  
  return ContentService.createTextOutput("Order Logged Successfully");
}
