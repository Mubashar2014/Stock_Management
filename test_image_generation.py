"""Test script for image generation."""
from app import create_app
from app.models import StockIn, StockOut, Supplier, Customer
from app.utils import create_receipt_image, create_khata_statement_image, save_temp_image
import os

app = create_app()

with app.app_context():
    print("🧪 Testing Image Generation...")
    print("-" * 50)
    
    # Test 1: Stock In Receipt
    print("\n1. Testing Stock In Receipt Image...")
    stock_in = StockIn.query.first()
    if stock_in:
        try:
            image_bytes = create_receipt_image(stock_in, 'stock_in')
            temp_path = save_temp_image(image_bytes, 'test_stock_in')
            size_kb = len(image_bytes) / 1024
            print(f"   ✅ Generated: {size_kb:.1f} KB")
            print(f"   📁 Saved to: {temp_path}")
            os.unlink(temp_path)
            print(f"   🗑️  Cleaned up temp file")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ⚠️  No Stock In records found")
    
    # Test 2: Stock Out Receipt
    print("\n2. Testing Stock Out Receipt Image...")
    stock_out = StockOut.query.first()
    if stock_out:
        try:
            image_bytes = create_receipt_image(stock_out, 'stock_out')
            temp_path = save_temp_image(image_bytes, 'test_stock_out')
            size_kb = len(image_bytes) / 1024
            print(f"   ✅ Generated: {size_kb:.1f} KB")
            print(f"   📁 Saved to: {temp_path}")
            os.unlink(temp_path)
            print(f"   🗑️  Cleaned up temp file")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ⚠️  No Stock Out records found")
    
    # Test 3: Supplier Khata Statement
    print("\n3. Testing Supplier Khata Statement Image...")
    supplier = Supplier.query.first()
    if supplier:
        try:
            image_bytes = create_khata_statement_image(supplier, 'supplier')
            temp_path = save_temp_image(image_bytes, 'test_supplier_khata')
            size_kb = len(image_bytes) / 1024
            print(f"   ✅ Generated: {size_kb:.1f} KB")
            print(f"   📁 Saved to: {temp_path}")
            os.unlink(temp_path)
            print(f"   🗑️  Cleaned up temp file")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ⚠️  No Suppliers found")
    
    # Test 4: Customer Khata Statement
    print("\n4. Testing Customer Khata Statement Image...")
    customer = Customer.query.first()
    if customer:
        try:
            image_bytes = create_khata_statement_image(customer, 'customer')
            temp_path = save_temp_image(image_bytes, 'test_customer_khata')
            size_kb = len(image_bytes) / 1024
            print(f"   ✅ Generated: {size_kb:.1f} KB")
            print(f"   📁 Saved to: {temp_path}")
            os.unlink(temp_path)
            print(f"   🗑️  Cleaned up temp file")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ⚠️  No Customers found")
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("\n💡 Now you can:")
    print("   1. Run the Flask app: python run.py")
    print("   2. Go to Stock In/Out list pages")
    print("   3. Click WhatsApp button")
    print("   4. Receipt image will download automatically")
    print("   5. Share the downloaded image on WhatsApp!")
