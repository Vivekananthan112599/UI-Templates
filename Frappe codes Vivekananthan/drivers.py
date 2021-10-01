# -*- coding: utf-8 -*-
# Copyright (c) 2018, info@valiantsystems.com and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from ecommerce_business_store.ecommerce_business_store.doctype.customers.customers import update_password
from datetime import date, datetime, time
from frappe.utils import getdate, add_months, add_to_date, nowdate, today, now
from ecommerce_business_store.utils.setup import get_settings_from_domain
from ecommerce_business_store.ecommerce_business_store.api import check_domain

class Drivers(Document):
	def validate(self):
		if self.get('__islocal'):
			check_drivers = frappe.db.get_all('User', filters={'name': self.driver_email})
			# check_drivers = frappe.db.get_all('Drivers', filters={'driver_email': self.driver_email, 'name': ('!=', self.name)})
			if check_drivers:
				user_role=frappe.db.get_all('Has Role',filters={'parent':self.driver_email,'role':'Driver'}) 							
				if not user_role:
					add_arole(self,'Driver')
				else:
					frappe.throw(frappe._('E-Mail ID already registered.'))
				# frappe.throw(frappe._('E-Mail ID already registered.'))
		if self.driver_phone:
			self.validate_phone()
		if self.set_new_password:
			self.validate_pwd()
		self.validate_status_change()

	def remove_duplicate_business(self):
		for x in self.business_list:
			check_existing = frappe.db.get_all("Driver Business Mapping",filters={"parent":self.name,"business":x.business})
			if check_existing:
				index = 0
				for existing_record in check_existing:
					if index!=0:
						frappe.db.sql("""DELETE FROM `tabDriver Business Mapping` WHERE name=%(name)s""",{"name":existing_record.name})
						frappe.db.commit()
					index = index + 1
			
	def business_names(self):
		if self.business_list:
			business_names = ""
			for x in self.business_list:
				business_names+= frappe.db.get_value("Business",x.business,"restaurant_name")+","
			self.mapped_business = business_names[:-1]
		else:
			self.mapped_business = ""
	def validate_status_change(self):
		prev_status = frappe.db.get_value('Drivers', self.name, 'working_status')
		if self.working_status == 'Available' and prev_status == 'On Duty':
			check_orders_list = frappe.db.sql('''select name from `tabOrder` where driver = %(driver)s and status not in ("Completed", "Cancelled")''', {'driver': self.name}, as_dict=1)
			if check_orders_list:
				frappe.throw(frappe._('Status cannot be changed to Available.'))
		
	# def check_driver_state(self):
	# 	prev_state = frappe.db.get_value('Drivers', self.name, 'driver_status')
	# 	if prev_state != self.driver_status or prev_status != self.working_status:
	# 		frappe.publish_realtime('check_active_drivers', {'name': self.name, 'driver_status': self.driver_status, 'working_status': self.working_status})

	def validate_phone(self):
		import re
		res = re.search('(?=.*\d)[\d]', str(self.driver_phone))
		if not res:
			frappe.throw(frappe._('Phone number must contain only numbers'))
		order_settings = get_settings_from_domain('Order Settings')
		if order_settings.enable_phone_validation:
			if len(str(self.driver_phone)) != int(order_settings.max_phone_length):
				frappe.throw(frappe._('Phone Number must contain {0} digits').format(order_settings.max_phone_length))

	def validate_pwd(self):
		order_settings = get_settings_from_domain('Order Settings')
		if len(self.set_new_password) < int(order_settings.min_password_length):
			frappe.throw(frappe._('Password must contain {0} digits').format(order_settings.min_password_length))
		from ecommerce_business_store.ecommerce_business_store.doctype.order_settings.order_settings import validate_password
		validate_password(self.set_new_password)

	def on_update(self):	
		if self.driver_status == 'Offline':
			self.working_status = "Unavailable"
		# else:
		# 	self.working_status = "Available"
		if self.set_new_password:
			self.new_password = self.set_new_password
		if self.driver_email:
			s = frappe.db.get_all("User", fields=["full_name","email","mobile_no"] , filters={"email": self.driver_email},limit_page_length=1)
			if s:				
				update_user(self)
				if self.set_new_password:
					update_password(new_password=self.new_password,user=self.name)
					frappe.db.set_value('Drivers', self.name, 'set_new_password','')
			else:					
				d = frappe.db.sql("""select name from `tabUser` where email=%(email)s""",{'email':self.driver_email})
				if d:
					user_role=frappe.db.get_all('Has Role',filters={'parent':self.driver_email,'role':'Driver'}) 							
					if not user_role:
						add_arole(self,'Driver')
					else:
						frappe.throw("Email id already registered")
				else:					
					user = insert_user(self)
					if user:
						if self.new_password:
							newupdate = update_password(new_password=self.new_password, old_password=None,user=self.driver_email)								
							frappe.db.set_value('Drivers', self.name, 'set_new_password','')
		# self.check_driver_state()
		frappe.publish_realtime('check_active_drivers', {'name': self.name, 'driver_status': self.driver_status, 'working_status': self.working_status,'business_list':self.business_list})
		# self.remove_duplicate_business()
		# self.business_names()
def update_user(self):	
	# frappe.db.set_value("User", self.driver_email , "first_name", self.driver_name)
	# frappe.db.set_value("User", self.driver_email , "mobile_no", self.driver_phone)
	# frappe.db.set_value("User", self.driver_email , "location", self.location)
	# frappe.db.set_value("User", self.driver_email , "birth_date", self.birth_date)
	# frappe.db.set_value("User", self.driver_email , "gender", self.gender)
	add_arole(self,'Driver')
		
@frappe.whitelist()
def add_arole(self,role):	
	user_role=frappe.db.get_all('Has Role',filters={'parent':self.driver_email,'role':role})
	if not user_role:
		result = frappe.get_doc({
			"doctype": "Has Role",
			"name": nowdate(),
			"parent": self.driver_email,
			"parentfield": "roles",
			"parenttype": "User",
			"role": role
			}).insert()
		
@frappe.whitelist(allow_guest=True)
def insert_user(self):	
	from frappe.utils import random_string	
	result= frappe.get_doc({
		"doctype": "User","email": self.driver_email,"first_name": self.driver_name,
		"mobile_no": self.driver_phone,"send_welcome_email": 0,
		"gender": self.gender,"birth_date": self.birth_date,"location": self.location
	}).insert(ignore_permissions=True)
	add_arole(self,'Driver')
	return result		

@frappe.whitelist()
def get_shipping_manager():
	shipping_info = ''
	installed_apps = frappe.db.sql(''' select * from `tabModule Def` where app_name='shipping_providers' ''', as_dict=True)
	if len(installed_apps) > 0 and not check_domain('restaurant'):
		user = frappe.session.user
		if "Shipping Manager" in frappe.get_roles(user):
			shipping_provider = frappe.db.get_all('Shipping Provider',filters={'email':user},fields=['name'])
			if shipping_provider:
				shipping_info = shipping_provider[0].name
	return shipping_info

def get_query_condition(user):
	installed_apps = frappe.db.sql(''' select * from `tabModule Def` where app_name='shipping_providers' ''', as_dict=True)
	if len(installed_apps) > 0 and not check_domain('restaurant'):
		if not user: user = frappe.session.user
		if "Shipping Manager" in frappe.get_roles(user):
			shipping_provider = frappe.db.get_all('Shipping Provider',filters={'email':user},fields=['name'])
			if shipping_provider:
				return "(`tabDrivers`.shipping_provider='{0}'  )".format(shipping_provider[0].name)

def has_permission(doc, user):
	installed_apps = frappe.db.sql(''' select * from `tabModule Def` where app_name='shipping_providers' ''', as_dict=True)
	if len(installed_apps) > 0 and not check_domain('restaurant'):
		if not user: user = frappe.session.user
		if "Shipping Manager" in frappe.get_roles(user):
			shipping_provider = frappe.db.get_all('Shipping Provider',filters={'email':user},fields=['name'])
			if shipping_provider:
				if doc.shipping_provider == shipping_provider[0].name:
					return True
				else:
					return False
@frappe.whitelist(allow_guest=True)
def get_all_business_list():
	condition = ''
	if check_domain("restaurant"):
		return frappe.db.sql("""SELECT name FROM `tabBusiness` WHERE disable = 0  AND show_in_website = 1 AND publish_in_market_place = 1""",as_dict=1)
	return frappe.db.sql("""SELECT name FROM `tabBusiness` WHERE disable = 0 """,as_dict=1)

@frappe.whitelist(allow_guest=True)
def get_active_business_list():
	condition = ''
	if check_domain("restaurant"):
		return {"list_name":frappe.db.sql("""SELECT name,restaurant_name FROM `tabBusiness` WHERE disable = 0  AND show_in_website = 1 AND publish_in_market_place = 1""",as_dict=1)}
	return {"list_name":frappe.db.sql("""SELECT name,restaurant_name FROM `tabBusiness` WHERE disable = 0 """,as_dict=1)}

@frappe.whitelist(allow_guest=True)
def remove_duplicate(driver_id,business_list):
	business_list_array = []
	driver_business = frappe.db.sql("SELECT name FROM `tabDriver Business Mapping` WHERE parent=%(driver_id)s",{"driver_id":driver_id},as_dict=1)
	for x in driver_business:
		frappe.db.sql("""DELETE FROM `tabDriver Business Mapping` WHERE name=%(name)s""",{"name":x.name})
		frappe.db.commit()
	for x in json.loads(business_list):
		bundle_order_item = frappe.get_doc({
											'doctype': 'Driver Business Mapping',
											'parent':driver_id,
											'parentfield': "business_list",
											'parenttype': "Drivers",
											'business':x.get("business")
											}).insert(ignore_permissions=True)
		business_list_array.append(x.get("business"))
	driver_info = frappe.get_doc("Drivers",driver_id)
	business_names = ""
	if driver_info.business_list:
		business_names = ""
		for x in driver_info.business_list:
			business_names+= frappe.db.get_value("Business",x.business,"restaurant_name")+",<br/>"
		driver_info.mapped_business = business_names[:-6]
	else:
		driver_info.mapped_business = ""
	driver_info.save()
	return business_list_array



//-----------------------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def make_payment(source_name=None, target_doc=None, order=None, mode_of_payment=None, amount=None, vendor_order=None):
	
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive" if flt(source.outstanding_amount) > flt(0) else "Pay"
	if pe.payment_type == 'Pay':
		pe.payment_type = 'Receive'
		check_prev_payments = frappe.db.sql('''select ifnull(sum(allocated_amount), 0) from `tabPayment Reference` 
			pr inner join `tabPayment Entry` pe on pe.name = pr.parent where pe.payment_type = "Receive" 
			and reference_doctype = "Order" and reference_name = %(ref)s''', {'ref': source_name})
		if check_prev_payments and check_prev_payments[0]:
			if float(check_prev_payments[0][0]) > 0:
				pe.payment_type = 'Pay'
	pe.restaurant = source.business
	# pe.cost_center = doc.get("cost_center")
	pe.posting_date = nowdate()
	if mode_of_payment:
		pe.mode_of_payment = mode_of_payment
	else:
		pe.mode_of_payment = ""
	pe.party_type = source.customer_type
	pe.party = source.customer
	pe.party_name = source.customer_name
	pe.contact_person = ""
	pe.contact_email = ""
	if amount:
		pe.paid_amount = (amount)
		pe.base_paid_amount = (amount)
		pe.received_amount = (amount)
		paid_amount=amount
	else:
		pe.paid_amount = abs(total)
		pe.base_paid_amount = abs(total)
		pe.received_amount = abs(total)
		paid_amount = abs(total)
	pe.allocate_payment_amount = 1
	payment_type = 'received from'
	if pe.payment_type == 'Pay':
		payment_type = 'paid to'
	pe.remarks = 'Amount {0} {1} {2} {3}'.format(default_currency.default_currency, pe.paid_amount, payment_type, pe.party)
	pe.append("references", {
		'reference_doctype':"Order",
		'reference_name': source.name,
		"bill_no": "",
		"due_date": source.order_date,
		'total_amount': abs(total),
		'outstanding_amount': 0,
		'allocated_amount': paid_amount
	})
	return pe

 frappe.model.open_mapped_doc({
            method: "ecommerce_business_store.accounts.api.make_payment",
            frm: cur_frm
        })
