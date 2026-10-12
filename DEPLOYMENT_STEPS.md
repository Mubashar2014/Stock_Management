# Deployment Steps for Stock Management System Fixes

## Pre-Deployment Checklist

### 1. Backup Your Database
```bash
# MySQL backup
mysqldump -u root -p stock_management > backup_before_fixes_$(date +%Y%m%d_%H%M%S).sql
```

---

## Deployment Steps

### Step 1: Update Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `reportlab==4.0.9` - PDF generation with Unicode/Urdu support
- `arabic-reshaper==0.1.1` - Arabic/Urdu text reshaping for PDF

### Step 2: Apply Database Migration
```bash
# Generate migration (if needed)
flask db migrate -m "Change balance columns to Numeric for precision"

# Apply migration
flask db upgrade
```

The migration will:
- Convert `Supplier.opening_balance` from Float to Numeric(12,2)
- Convert `Supplier.current_balance` from Float to Numeric(12,2)
- Convert `Customer.opening_balance` from Float to Numeric(12,2)
- Convert `Customer.current_balance` from Float to Numeric(12,2)

### Step 3: Restart Your Application
```bash
# If using development server
pkill -f "flask run"
flask run

# If using production server (gunicorn)
systemctl restart gunicorn
# or
supervisorctl restart stock_management
```

---

## Verification Steps

### 1. Test App Imports
```bash
python -c "import sys; sys.path.insert(0, '.'); from app import create_app; app = create_app(); print('✓ App imports successfully')"
```

### 2. Test Receipt Generation
1. Go to Stock In or Stock Out list
2. Click "Download Receipt" on any entry
3. Verify file downloads as `.pdf` (not `.png`)
4. Open PDF and verify all Urdu text displays correctly

### 3. Test Balance Updates
1. Create a new stock transaction
2. Verify supplier/customer balance updates
3. Edit the transaction (especially changing supplier/customer)
4. Verify balance reversal works correctly
5. Delete the transaction
6. Verify balance is restored

### 4. Test Error Handling
1. Try accessing a non-existent page (`/nonexistent`)
2. Should see 404 error page (in Urdu)
3. Check application logs for errors
4. Pages should load normally without random 500 errors

---

## Rollback Steps (If Needed)

### Rollback Database Migration
```bash
# Go back one migration
flask db downgrade
```

### Revert Code Changes
```bash
git revert HEAD  # If you want to revert the most recent commit
# or
git checkout <previous-commit-hash>  # To go to a specific previous version
```

---

## Configuration Notes

### Environment Variables (Optional)
If you want to use environment-specific configuration:

```bash
# .env file
export FLASK_ENV=production
export DATABASE_URL=mysql+mysqlconnector://user:password@host/database
export SECRET_KEY=your-secret-key-here
```

### Important Settings in app/config.py
- `SQLALCHEMY_DATABASE_URI` - Database connection string
- `UPLOAD_FOLDER` - Where uploaded files are stored
- `MAX_CONTENT_LENGTH` - Maximum file upload size (16MB)
- `PERMANENT_SESSION_LIFETIME` - Session duration (7 days)

---

## Monitoring & Logging

After deployment, monitor these things:

### 1. Check Application Logs
```bash
# If using systemd
journalctl -u gunicorn -f

# If using screen/tmux
tail -f app.log
```

### 2. Database Health
```bash
# Check table status
mysql> SHOW TABLE STATUS FROM stock_management;

# Verify balance columns
mysql> DESCRIBE suppliers;
mysql> DESCRIBE customers;
```

### 3. Test All Main Features
- [ ] Login/logout
- [ ] Add supplier/customer
- [ ] Create stock in/out transactions
- [ ] Download receipts as PDF
- [ ] View khata statements
- [ ] View cashbook
- [ ] View profit report

---

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'reportlab'"
**Solution:** Run `pip install -r requirements.txt` again

### Issue: "Database migration fails"
**Solution:** 
```bash
# Check current migration version
flask db current

# If stuck, manually downgrade and upgrade
flask db downgrade
flask db upgrade
```

### Issue: "PDF downloads as empty file"
**Solution:** 
- Verify Urdu font is installed: `fc-list | grep Noto`
- If not installed, install it: `sudo apt install fonts-noto-cjk fonts-noto-cjk-extra`

### Issue: "Balance still shows old values after editing"
**Solution:** 
- This should not happen after the fix
- If it does, run the fix_balances.py script:
```bash
python fix_balances.py
```

---

## Performance Optimization (Optional)

### Database Connection Pool
The app now uses connection pooling with these settings:
- Pool size: 10 connections
- Pool recycle: 3600 seconds (1 hour)
- Pre-ping: Enabled (verifies connection before use)

This automatically handles stale connections and improves performance.

---

## Next Steps

1. Test all three fixes thoroughly in development
2. Deploy to staging environment
3. Run full regression testing
4. Deploy to production during off-peak hours
5. Monitor for 24 hours after deployment
6. Celebrate! 🎉
