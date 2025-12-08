# IAT AIRLINES - TEST CASES FOR FAMILY, GUEST BOOKING, CANCELLATION & RESCHEDULING

## TEST CASE 1: FAMILY MEMBER MANAGEMENT
### Prerequisites:
- Create 2 test user accounts first
- User A (Initiator): Ali Khan (ali.khan@example.com)
- User B (Recipient): Ayesha Ahmed (ayesha.ahmed@example.com)

### Test 1.1: Send Family Invitation
**Steps:**
1. Login as User A (Ali Khan)
2. Go to Account → Family Members
3. Click "Add Family Member"
4. Search for "Ayesha Ahmed"
5. Select Relationship: "Spouse"
6. Click "Send Invitation"

**Expected Result:**
- Success message appears
- Invitation status shows "PENDING"
- User B receives notification

---

### Test 1.2: Accept Family Invitation
**Steps:**
1. Logout and login as User B (Ayesha Ahmed)
2. Go to Account → Family Requests
3. See invitation from Ali Khan
4. Click "Accept"

**Expected Result:**
- Status changes to "ACCEPTED"
- User A can now see Ayesha as family member
- Ayesha can now see Ali as reciprocal family member

---

### Test 1.3: Reject Family Invitation
**Steps:**
1. Create another test user C (Usman Malik)
2. User A sends invitation to User C
3. Login as User C
4. Go to Family Requests
5. Click "Reject"

**Expected Result:**
- Status changes to "REJECTED"
- User A cannot see User C in family members
- User C won't see future invitations from User A (unless re-invited)

---

### Test 1.4: Add From Past Bookings (Using Family Member)
**Steps:**
1. Login as User A (who now has Ayesha as accepted family member)
2. Search for a flight and select it
3. At Passenger Information step, click "Add Myself"
4. Then click "Add Family Member" for second passenger
5. Select "Ayesha Ahmed" from family list
6. System should pre-fill her information
7. Complete booking

**Expected Result:**
- Ayesha's details auto-filled from family profile
- Booking created successfully
- Both passengers listed in confirmation

---

## TEST CASE 2: GUEST BOOKING (NO ACCOUNT)
### Test 2.1: Complete Booking Without Login
**Steps:**
1. Do NOT login (clear session/logout)
2. Go to homepage
3. Search for a flight
4. Select a flight
5. At Passenger Information:
   - Enter: Ahmed Khan, DOB: 1990-05-15, Passport: AB1234567, Male, Title: MR
6. Select seat (e.g., 15A in Economy)
7. Review booking summary
8. At Payment:
   - Enter contact email: guest@example.com
   - Enter emergency phone: 03001234567
   - Complete payment

**Expected Result:**
- Booking created with Lead_User_ID = NULL
- PNR generated successfully
- Confirmation email sent to guest@example.com
- Ticket shows booking reference number
- Status shows "CONFIRMED"

---

### Test 2.2: Guest Cannot Manage Booking Without PNR
**Steps:**
1. As guest (logged out), try to access "Manage Bookings"
2. System should ask for:
   - Booking Reference (PNR)
   - Email address

**Expected Result:**
- Can only access booking via PNR + email verification
- No account access possible

---

## TEST CASE 3: FLIGHT CANCELLATION
### Test 3.1: Cancel Single Passenger Reservation
**Prerequisites:**
- Have a completed booking with 1+ reservations
- Flight departure is >48 hours away (for refund eligibility)

**Steps:**
1. Login as user with booking
2. Go to "Manage Bookings" → Find booking
3. Click "Cancel Booking"
4. Select which passenger(s) to cancel
5. Confirm cancellation

**Expected Result:**
- Reservation status changes to "CANCELLED"
- Refund amount calculated (should appear on screen)
- Cancellation log entry created
- Email confirmation sent

---

### Test 3.2: Cancel All Passengers (Entire Booking)
**Steps:**
1. Same as 3.1, but cancel ALL passengers
2. Confirm

**Expected Result:**
- All reservations marked "CANCELLED"
- Booking status changes from "CONFIRMED" to "CANCELLED"
- Full refund calculated
- Cancellation_Log has multiple entries (one per reservation)

---

### Test 3.3: Partial Cancellation (Multi-passenger)
**Steps:**
1. Booking with 3 passengers
2. Cancel only 2 passengers, keep 1
3. Confirm

**Expected Result:**
- 2 reservations → "CANCELLED"
- 1 reservation → "ISSUED" (active)
- Booking status → "CONFIRMED" (still active because some passengers remain)
- Refund = only cancelled passengers' amounts

---

## TEST CASE 4: FLIGHT RESCHEDULING
### Test 4.1: Reschedule to Different Flight
**Prerequisites:**
- Active booking with at least 1 reservation
- Different flight available on different date
- Departure >24 hours away

**Steps:**
1. Login and go to Manage Bookings
2. Click "Reschedule Booking"
3. Search new flight (different date/time)
4. Select new flight
5. Choose new seats from seat map
6. Review changes and price difference
7. Pay any additional fees (or receive refund if cheaper)
8. Confirm

**Expected Result:**
- Old reservation marked as rescheduled
- New reservation created with same passenger
- Price difference applied (if flight costs more/less)
- Booking stays "CONFIRMED"
- Change fee: 500 PKR per passenger (if applicable)

---

### Test 4.2: Reschedule to Same Flight Different Seat
**Steps:**
1. Same booking
2. Reschedule but select same flight, different seat
3. Complete

**Expected Result:**
- Seat changes in reservation
- No price difference (same flight)
- Change fee may still apply
- Reservation status updated

---

### Test 4.3: Reschedule Multi-leg Round Trip
**Steps:**
1. Round trip booking (outbound + return)
2. Reschedule both legs to new dates
3. Select new seats for both
4. Review total price change
5. Confirm

**Expected Result:**
- Both original reservations rescheduled
- 2 new reservations created
- Price difference calculated across both legs
- Booking remains "CONFIRMED"

---

## TEST CASE 5: FEE & REFUND TRACKING IN DATABASE
### Test 5.1: Cancellation Refund Recording
**After completing Test 3.1:**
- Check `Cancellation_Log` table for refund amount
- Check `Payment` table for original amount
- Verify calculation

**SQL to run:**
```sql
SELECT * FROM Cancellation_Log 
WHERE Booking_ID = '<YOUR_BOOKING_ID>'
ORDER BY Cancellation_Date DESC;
```

---

### Test 5.2: Rescheduling Fee Recording
**After completing Test 4.1:**
- Check if change fee (500 PKR per passenger) recorded
- Check if price difference recorded
- Verify total charges

**SQL to run:**
```sql
SELECT r.Reservation_ID, r.Price_Charged, 
       CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN 'YES' ELSE 'NO' END as Was_Rescheduled
FROM Reservation r
WHERE r.Booking_ID = '<YOUR_BOOKING_ID>'
ORDER BY r.Reservation_ID;
```

---

## SUMMARY TEST EXECUTION PLAN

### Phase 1: Family Features (30 mins)
- [ ] Create 3 test users
- [ ] Test 1.1: Send invitation
- [ ] Test 1.2: Accept invitation
- [ ] Test 1.3: Reject invitation
- [ ] Test 1.4: Book using family member

### Phase 2: Guest Booking (15 mins)
- [ ] Test 2.1: Complete guest booking
- [ ] Test 2.2: Manage guest booking via PNR

### Phase 3: Cancellation (30 mins)
- [ ] Test 3.1: Single passenger cancellation
- [ ] Test 3.2: Full booking cancellation
- [ ] Test 3.3: Partial cancellation

### Phase 4: Rescheduling (30 mins)
- [ ] Test 4.1: Reschedule to different flight
- [ ] Test 4.2: Reschedule same flight different seat
- [ ] Test 4.3: Reschedule round trip

### Phase 5: Database Verification (15 mins)
- [ ] Run cancellation verification queries
- [ ] Run rescheduling verification queries
- [ ] Check fee calculations
