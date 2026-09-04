# M1 Dataset Schema Snapshot

This document is generated directly from the frozen M1 raw dataset.
It is a reference artifact for M2 ingestion/normalization design.

## `accounting/journal_entries.csv`

**Rows:** approximately 760,412

### Columns

| # | Column |
|---:|---|
| 1 | `journal_entry_id` |
| 2 | `line_number` |
| 3 | `timestamp` |
| 4 | `source_system` |
| 5 | `source_record_id` |
| 6 | `account_id` |
| 7 | `counterparty_id` |
| 8 | `debit` |
| 9 | `credit` |
| 10 | `currency` |
| 11 | `description` |
| 12 | `reference_id` |
| 13 | `status` |

### Sample rows

```csv
journal_entry_id,line_number,timestamp,source_system,source_record_id,account_id,counterparty_id,debit,credit,currency,description,reference_id,status
JRN_000001,1,2025-09-23T17:54:47,commerce_invoices,INV_000001,AR_CUSTOMERS,CUST_000937,390.58,0.00,INR,Customer invoice recognized,ORD_000001,POSTED
JRN_000001,2,2025-09-23T17:54:47,commerce_invoices,INV_000001,REVENUE_SALES,CUST_000937,0.00,331.00,INR,Customer invoice recognized,ORD_000001,POSTED
JRN_000001,3,2025-09-23T17:54:47,commerce_invoices,INV_000001,GST_OUTPUT_PAYABLE,,0.00,59.58,INR,Customer invoice recognized,ORD_000001,POSTED
JRN_000002,1,2025-09-13T19:11:51,commerce_invoices,INV_000002,AR_CUSTOMERS,CUST_005923,390.58,0.00,INR,Customer invoice recognized,ORD_000002,POSTED
JRN_000002,2,2025-09-13T19:11:51,commerce_invoices,INV_000002,REVENUE_SALES,CUST_005923,0.00,331.00,INR,Customer invoice recognized,ORD_000002,POSTED
```

## `banking/bank_transactions.csv`

**Rows:** approximately 8,679

### Columns

| # | Column |
|---:|---|
| 1 | `bank_transaction_id` |
| 2 | `account_id` |
| 3 | `transaction_date` |
| 4 | `value_date` |
| 5 | `amount` |
| 6 | `currency` |
| 7 | `direction` |
| 8 | `transaction_type` |
| 9 | `description` |
| 10 | `reference_id` |
| 11 | `counterparty_id` |
| 12 | `status` |

### Sample rows

```csv
bank_transaction_id,account_id,transaction_date,value_date,amount,currency,direction,transaction_type,description,reference_id,counterparty_id,status
BANK_000001,BANK_002,2025-09-02T19:03:11,2025-09-02T19:03:11,48538.62,INR,CREDIT,PAYMENT_GATEWAY_SETTLEMENT,PayFlow settlement SET_000003,SET_000003,PAYFLOW,POSTED
BANK_000002,BANK_002,2025-09-02T22:13:59,2025-09-02T22:13:59,2597.18,INR,DEBIT,CUSTOMER_REFUND,Customer refund REF_000339,REF_000339,CUST_007222,POSTED
BANK_000003,BANK_002,2025-09-02T22:29:39,2025-09-02T22:29:39,1230.98,INR,DEBIT,CUSTOMER_REFUND,Customer refund REF_000094,REF_000094,CUST_000154,POSTED
BANK_000004,BANK_002,2025-09-03T04:34:28,2025-09-03T04:34:28,48514.34,INR,CREDIT,PAYMENT_GATEWAY_SETTLEMENT,PayFlow settlement SET_000010,SET_000010,PAYFLOW,POSTED
BANK_000005,BANK_002,2025-09-04T01:43:05,2025-09-04T01:43:05,2293.09,INR,DEBIT,CUSTOMER_REFUND,Customer refund REF_000394,REF_000394,CUST_005452,POSTED
```

## `commerce/invoices.csv`

**Rows:** approximately 157,461

### Columns

| # | Column |
|---:|---|
| 1 | `invoice_id` |
| 2 | `order_id` |
| 3 | `customer_id` |
| 4 | `invoice_date` |
| 5 | `gross_amount` |
| 6 | `discount` |
| 7 | `tax` |
| 8 | `shipping_fee` |
| 9 | `net_amount` |
| 10 | `invoice_status` |
| 11 | `currency` |

### Sample rows

```csv
invoice_id,order_id,customer_id,invoice_date,gross_amount,discount,tax,shipping_fee,net_amount,invoice_status,currency
INV_000001,ORD_000001,CUST_000937,2025-09-23T17:54:47,282.00,0.00,59.58,49.00,390.58,ISSUED,INR
INV_000002,ORD_000002,CUST_005923,2025-09-13T19:11:51,282.00,0.00,59.58,49.00,390.58,ISSUED,INR
INV_000003,ORD_000003,CUST_005083,2025-09-25T22:38:07,727.00,36.35,133.14,49.00,872.79,RETURNED,INR
INV_000004,ORD_000004,CUST_002356,2025-09-19T19:46:22,902.00,0.00,171.18,49.00,1122.18,ISSUED,INR
INV_000005,ORD_000005,CUST_001867,2025-09-10T23:30:14,266.00,26.60,55.51,69.00,363.91,ISSUED,INR
```

## `commerce/orders.csv`

**Rows:** approximately 157,461

### Columns

| # | Column |
|---:|---|
| 1 | `order_id` |
| 2 | `customer_id` |
| 3 | `order_date` |
| 4 | `gross_amount` |
| 5 | `discount` |
| 6 | `tax` |
| 7 | `shipping_fee` |
| 8 | `net_amount` |
| 9 | `order_status` |
| 10 | `payment_method_selected` |
| 11 | `fulfillment_hub` |
| 12 | `invoice_date` |
| 13 | `delivered_date` |
| 14 | `sku_lines` |

### Sample rows

```csv
order_id,customer_id,order_date,gross_amount,discount,tax,shipping_fee,net_amount,order_status,payment_method_selected,fulfillment_hub,invoice_date,delivered_date,sku_lines
ORD_000001,CUST_000937,2025-09-23T16:08:47,282.00,0.00,59.58,49.00,390.58,DELIVERED,UPI,MUMBAI,2025-09-23T17:54:47,2025-10-01T03:54:47,"[{""product_id"":""PROD_000281"",""quantity"":1,""unit_price"":""282.00"",""line_total"":""282.00""}]"
ORD_000002,CUST_005923,2025-09-13T18:17:51,282.00,0.00,59.58,49.00,390.58,DELIVERED,UPI,MUMBAI,2025-09-13T19:11:51,2025-09-18T00:11:51,"[{""product_id"":""PROD_000281"",""quantity"":1,""unit_price"":""282.00"",""line_total"":""282.00""}]"
ORD_000003,CUST_005083,2025-09-25T20:34:07,727.00,36.35,133.14,49.00,872.79,RETURNED,CARD,DELHI_NCR,2025-09-25T22:38:07,2025-09-28T04:38:07,"[{""product_id"":""PROD_000166"",""quantity"":1,""unit_price"":""201.00"",""line_total"":""201.00""},{""product_id"":""PROD_000197"",""quantity"":1,""unit_price"":""526.00"",""line_total"":""526.00""}]"
ORD_000004,CUST_002356,2025-09-19T17:23:22,902.00,0.00,171.18,49.00,1122.18,DELIVERED,UPI,BENGALURU,2025-09-19T19:46:22,2025-09-27T03:46:22,"[{""product_id"":""PROD_000133"",""quantity"":1,""unit_price"":""902.00"",""line_total"":""902.00""}]"
ORD_000005,CUST_001867,2025-09-10T20:03:14,266.00,26.60,55.51,69.00,363.91,DELIVERED,UPI,MUMBAI,2025-09-10T23:30:14,2025-09-18T06:30:14,"[{""product_id"":""PROD_000285"",""quantity"":1,""unit_price"":""266.00"",""line_total"":""266.00""}]"
```

## `master/bank_accounts.csv`

**Rows:** approximately 4

### Columns

| # | Column |
|---:|---|
| 1 | `account_id` |
| 2 | `account_role` |
| 3 | `bank_name` |
| 4 | `ifsc` |
| 5 | `currency` |

### Sample rows

```csv
account_id,account_role,bank_name,ifsc,currency
BANK_001,Primary Operating Account,Indus Meridian Bank,IMBK0001001,INR
BANK_002,Payment Settlement Account,Indus Meridian Bank,IMBK0001002,INR
BANK_003,Vendor / Expense Account,Indus Meridian Bank,IMBK0001003,INR
BANK_004,Payroll / Statutory Account,Indus Meridian Bank,IMBK0001004,INR
```

## `master/customers.csv`

**Rows:** approximately 8,500

### Columns

| # | Column |
|---:|---|
| 1 | `customer_id` |
| 2 | `customer_name` |
| 3 | `city` |
| 4 | `state` |
| 5 | `postal_code` |
| 6 | `signup_date` |
| 7 | `preferred_payment_method` |

### Sample rows

```csv
customer_id,customer_name,city,state,postal_code,signup_date,preferred_payment_method
CUST_000001,Aarav Verma,Mumbai,Maharashtra,400001,2024-09-07,UPI
CUST_000002,Shreya Rao,Mumbai,Maharashtra,400001,2024-03-30,CARD
CUST_000003,Aarav Nair,Chennai,Tamil Nadu,600001,2024-08-11,UPI
CUST_000004,Riya Mehta,Bengaluru,Karnataka,560001,2026-01-03,CARD
CUST_000005,Priya Gupta,Visakhapatnam,Andhra Pradesh,530001,2025-04-04,CARD
```

## `master/employees.csv`

**Rows:** approximately 80

### Columns

| # | Column |
|---:|---|
| 1 | `employee_id` |
| 2 | `employee_name` |
| 3 | `department` |
| 4 | `designation` |
| 5 | `joining_date` |
| 6 | `monthly_gross` |

### Sample rows

```csv
employee_id,employee_name,department,designation,joining_date,monthly_gross
EMP_000001,Shreya Sharma,Marketing,Marketing Executive,2025-12-04,90000.00
EMP_000002,Pooja Gupta,Marketing,Marketing Manager,2024-10-27,33000.00
EMP_000003,Karan Pillai,Technology,Product Analyst,2026-04-18,153000.00
EMP_000004,Riya Kapoor,Technology,Product Analyst,2022-10-05,118000.00
EMP_000005,Rahul Singh,Warehouse,Warehouse Manager,2023-04-22,51000.00
```

## `master/payment_accounts.csv`

**Rows:** approximately 1

### Columns

| # | Column |
|---:|---|
| 1 | `payment_account_id` |
| 2 | `gateway_name` |
| 3 | `linked_bank_account_id` |
| 4 | `settlement_cycle` |
| 5 | `currency` |

### Sample rows

```csv
payment_account_id,gateway_name,linked_bank_account_id,settlement_cycle,currency
PAYACC_0001,PayFlow,BANK_002,T+1_TO_T+4,INR
```

## `master/products.csv`

**Rows:** approximately 350

### Columns

| # | Column |
|---:|---|
| 1 | `product_id` |
| 2 | `product_name` |
| 3 | `category` |
| 4 | `unit_price` |
| 5 | `cost_price` |

### Sample rows

```csv
product_id,product_name,category,unit_price,cost_price
PROD_000001,Planter 001,Home & Lifestyle Decor,2741.00,1507.55
PROD_000002,Travel Backpack 002,Apparel & Accessories,3992.00,2754.48
PROD_000003,Fast Charger 003,Electronics Accessories,1292.00,658.92
PROD_000004,Hair Serum 004,Personal Care & Wellness,445.00,204.70
PROD_000005,Casual Shirt 005,Apparel & Accessories,554.00,332.40
```

## `master/tax_accounts.csv`

**Rows:** approximately 2

### Columns

| # | Column |
|---:|---|
| 1 | `tax_account_id` |
| 2 | `tax_type` |
| 3 | `filing_frequency` |
| 4 | `currency` |

### Sample rows

```csv
tax_account_id,tax_type,filing_frequency,currency
TAXACC_01,GST,MONTHLY,INR
TAXACC_02,TDS,MONTHLY,INR
```

## `master/vendors.csv`

**Rows:** approximately 150

### Columns

| # | Column |
|---:|---|
| 1 | `vendor_id` |
| 2 | `vendor_name` |
| 3 | `vendor_category` |
| 4 | `credit_period_days` |
| 5 | `gst_registered` |
| 6 | `handles_cod` |

### Sample rows

```csv
vendor_id,vendor_name,vendor_category,credit_period_days,gst_registered,handles_cod
VEND_000001,Crescent Lifestyle Manufacturing 001,GOODS,30,Y,N
VEND_000002,Bharat Home Supplies 002,GOODS,45,Y,N
VEND_000003,Deccan Consumer Goods 003,GOODS,30,Y,N
VEND_000004,Bharat Home Supplies 004,GOODS,30,Y,N
VEND_000005,Crescent Lifestyle Manufacturing 005,GOODS,30,Y,N
```

## `payments/payments.csv`

**Rows:** approximately 129,344

### Columns

| # | Column |
|---:|---|
| 1 | `payment_id` |
| 2 | `order_id` |
| 3 | `customer_id` |
| 4 | `payment_date` |
| 5 | `gateway` |
| 6 | `payment_method` |
| 7 | `amount` |
| 8 | `currency` |
| 9 | `status` |
| 10 | `gateway_reference` |

### Sample rows

```csv
payment_id,order_id,customer_id,payment_date,gateway,payment_method,amount,currency,status,gateway_reference
PAY_000001,ORD_000001,CUST_000937,2025-09-23T16:12:50,PayFlow,UPI,390.58,INR,SUCCESS,PF_00000001
PAY_000002,ORD_000002,CUST_005923,2025-09-13T18:18:57,PayFlow,UPI,390.58,INR,SUCCESS,PF_00000002
PAY_000003,ORD_000003,CUST_005083,2025-09-25T20:43:45,PayFlow,CARD,872.79,INR,SUCCESS,PF_00000003
PAY_000004,ORD_000004,CUST_002356,2025-09-19T17:31:58,PayFlow,UPI,1122.18,INR,SUCCESS,PF_00000004
PAY_000005,ORD_000005,CUST_001867,2025-09-10T20:11:06,PayFlow,UPI,363.91,INR,SUCCESS,PF_00000005
```

## `payments/refunds.csv`

**Rows:** approximately 5,343

### Columns

| # | Column |
|---:|---|
| 1 | `refund_id` |
| 2 | `order_id` |
| 3 | `payment_id` |
| 4 | `refund_date` |
| 5 | `refund_type` |
| 6 | `refund_reason` |
| 7 | `amount` |
| 8 | `currency` |
| 9 | `status` |
| 10 | `gateway` |
| 11 | `gateway_reference` |
| 12 | `customer_id` |

### Sample rows

```csv
refund_id,order_id,payment_id,refund_date,refund_type,refund_reason,amount,currency,status,gateway,gateway_reference,customer_id
REF_000001,ORD_000003,PAY_000003,2025-10-04T07:38:07,FULL,RETURNED_ORDER,872.79,INR,SUCCESS,PayFlow,RF_00000001,CUST_005083
REF_000002,ORD_000028,PAY_000028,2025-09-17T02:53:11,FULL,CUSTOMER_REQUEST,1690.70,INR,SUCCESS,PayFlow,RF_00000002,CUST_002435
REF_000003,ORD_000068,,2025-09-30T05:44:52,FULL,RETURNED_ORDER,2600.64,INR,SUCCESS,,,CUST_002782
REF_000004,ORD_000136,PAY_000112,2025-09-29T21:08:08,FULL,CUSTOMER_REQUEST,3628.50,INR,SUCCESS,PayFlow,RF_00000004,CUST_003808
REF_000005,ORD_000138,,2025-09-29T12:47:45,FULL,RETURNED_ORDER,908.60,INR,SUCCESS,,,CUST_000576
```

## `payroll/payroll.csv`

**Rows:** approximately 960

### Columns

| # | Column |
|---:|---|
| 1 | `payroll_id` |
| 2 | `employee_id` |
| 3 | `employee_name` |
| 4 | `department` |
| 5 | `designation` |
| 6 | `payroll_period` |
| 7 | `pay_date` |
| 8 | `gross_salary` |
| 9 | `employee_pf` |
| 10 | `professional_tax` |
| 11 | `tds` |
| 12 | `employee_deductions` |
| 13 | `net_pay` |
| 14 | `employer_pf` |
| 15 | `employer_esic` |
| 16 | `employer_contributions` |
| 17 | `total_employer_cost` |
| 18 | `currency` |
| 19 | `payment_account_id` |
| 20 | `status` |
| 21 | `bank_reference` |

### Sample rows

```csv
payroll_id,employee_id,employee_name,department,designation,payroll_period,pay_date,gross_salary,employee_pf,professional_tax,tds,employee_deductions,net_pay,employer_pf,employer_esic,employer_contributions,total_employer_cost,currency,payment_account_id,status,bank_reference
PYR_000001,EMP_000001,Shreya Sharma,Marketing,Marketing Executive,2025-09,2025-09-28,22000.00,1320.00,200.00,0.00,1520.00,20480.00,1320.00,0.00,1320.00,23320.00,INR,BANK_004,PAID,PAYROLL_00000001
PYR_000002,EMP_000002,Pooja Gupta,Marketing,Marketing Manager,2025-09,2025-09-28,55000.00,3300.00,200.00,666.67,4166.67,50833.33,3300.00,0.00,3300.00,58300.00,INR,BANK_004,PAID,PAYROLL_00000002
PYR_000003,EMP_000003,Karan Pillai,Technology,Product Analyst,2025-09,2025-09-28,36000.00,2160.00,200.00,0.00,2360.00,33640.00,2160.00,0.00,2160.00,38160.00,INR,BANK_004,PAID,PAYROLL_00000003
PYR_000004,EMP_000004,Riya Kapoor,Technology,Product Analyst,2025-09,2025-09-28,32000.00,1920.00,200.00,0.00,2120.00,29880.00,1920.00,0.00,1920.00,33920.00,INR,BANK_004,PAID,PAYROLL_00000004
PYR_000005,EMP_000005,Rahul Singh,Warehouse,Warehouse Manager,2025-09,2025-09-28,121000.00,7260.00,200.00,5850.00,13310.00,107690.00,7260.00,0.00,7260.00,128260.00,INR,BANK_004,PAID,PAYROLL_00000005
```

## `settlements/settlements.csv`

**Rows:** approximately 3,962

### Columns

| # | Column |
|---:|---|
| 1 | `settlement_id` |
| 2 | `settlement_date` |
| 3 | `gateway` |
| 4 | `currency` |
| 5 | `payment_count` |
| 6 | `gross_amount` |
| 7 | `refund_deductions` |
| 8 | `net_settlement_amount` |
| 9 | `destination_account_id` |
| 10 | `gateway_settlement_reference` |
| 11 | `first_payment_id` |
| 12 | `last_payment_id` |

### Sample rows

```csv
settlement_id,settlement_date,gateway,currency,payment_count,gross_amount,refund_deductions,net_settlement_amount,destination_account_id,gateway_settlement_reference,first_payment_id,last_payment_id
SET_000001,2025-09-05T22:04:10,PayFlow,INR,36,35148.41,340.31,34808.10,BANK_002,PFSET_00000001,PAY_004303,PAY_009474
SET_000002,2025-09-05T19:24:28,PayFlow,INR,34,49916.07,0.00,49916.07,BANK_002,PFSET_00000002,PAY_002034,PAY_002120
SET_000003,2025-09-02T19:03:11,PayFlow,INR,42,48538.62,0.00,48538.62,BANK_002,PFSET_00000003,PAY_000601,PAY_000873
SET_000004,2025-09-05T23:49:18,PayFlow,INR,35,54815.56,0.00,54815.56,BANK_002,PFSET_00000004,PAY_008124,PAY_004642
SET_000005,2025-09-04T22:10:31,PayFlow,INR,35,41559.86,2050.84,39509.02,BANK_002,PFSET_00000005,PAY_008106,PAY_005262
```

## `vendors/vendor_invoices.csv`

**Rows:** approximately 7,122

### Columns

| # | Column |
|---:|---|
| 1 | `vendor_invoice_id` |
| 2 | `vendor_id` |
| 3 | `vendor_category` |
| 4 | `invoice_date` |
| 5 | `due_date` |
| 6 | `invoice_type` |
| 7 | `description` |
| 8 | `subtotal` |
| 9 | `tax_amount` |
| 10 | `total_amount` |
| 11 | `currency` |
| 12 | `status` |
| 13 | `purchase_reference` |
| 14 | `handles_cod` |

### Sample rows

```csv
vendor_invoice_id,vendor_id,vendor_category,invoice_date,due_date,invoice_type,description,subtotal,tax_amount,total_amount,currency,status,purchase_reference,handles_cod
VINV_000001,VEND_000082,GOODS,2025-09-02T10:47:00,2025-10-17T10:47:00,GOODS,Packaging and merchandise supplies,74184.00,13353.12,87537.12,INR,APPROVED,PO_00000001,N
VINV_000002,VEND_000032,GOODS,2025-09-06T10:47:00,2025-10-06T10:47:00,GOODS,Inventory replenishment,103513.00,0.00,103513.00,INR,APPROVED,PO_00000002,N
VINV_000003,VEND_000087,GOODS,2025-09-04T10:37:00,2025-10-04T10:37:00,GOODS,Product stock replenishment,187964.00,33833.52,221797.52,INR,APPROVED,PO_00000003,N
VINV_000004,VEND_000005,GOODS,2025-09-04T10:13:00,2025-10-04T10:13:00,GOODS,Merchandise procurement,52811.00,9505.98,62316.98,INR,APPROVED,PO_00000004,N
VINV_000005,VEND_000065,GOODS,2025-09-02T10:35:00,2025-10-02T10:35:00,GOODS,Merchandise procurement,202815.00,36506.70,239321.70,INR,APPROVED,PO_00000005,N
```

## `vendors/vendor_payments.csv`

**Rows:** approximately 7,122

### Columns

| # | Column |
|---:|---|
| 1 | `vendor_payment_id` |
| 2 | `vendor_invoice_id` |
| 3 | `vendor_id` |
| 4 | `payment_date` |
| 5 | `payment_account_id` |
| 6 | `amount` |
| 7 | `currency` |
| 8 | `payment_method` |
| 9 | `status` |
| 10 | `bank_reference` |

### Sample rows

```csv
vendor_payment_id,vendor_invoice_id,vendor_id,payment_date,payment_account_id,amount,currency,payment_method,status,bank_reference
VPAY_000001,VINV_000001,VEND_000082,2025-10-17T20:34:00,BANK_003,87537.12,INR,BANK_TRANSFER,SUCCESS,VENDPAY_00000001
VPAY_000002,VINV_000002,VEND_000032,2025-10-06T22:55:00,BANK_003,103513.00,INR,BANK_TRANSFER,SUCCESS,VENDPAY_00000002
VPAY_000003,VINV_000003,VEND_000087,2025-10-04T21:14:00,BANK_003,221797.52,INR,BANK_TRANSFER,SUCCESS,VENDPAY_00000003
VPAY_000004,VINV_000004,VEND_000005,2025-10-04T19:18:00,BANK_003,62316.98,INR,BANK_TRANSFER,SUCCESS,VENDPAY_00000004
VPAY_000005,VINV_000005,VEND_000065,2025-10-02T20:10:00,BANK_003,239321.70,INR,BANK_TRANSFER,SUCCESS,VENDPAY_00000005
```

