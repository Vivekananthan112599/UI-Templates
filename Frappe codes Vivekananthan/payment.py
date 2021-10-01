# -*- coding: utf-8 -*-
# Copyright (c) 2019, sivaranjani and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _, scrub, ValidationError
from frappe.utils import flt, comma_or, nowdate, getdate
# from ecommerce_business_store.accounts.utils import make_accounting_entry, cancel_gl_entries
# from ecommerce_business_store.ecommerce_business_store.api import check_domain

class PaymentEntry(Document):
	def autoname(self): 
		from ecommerce_business_store.ecommerce_business_store.api import check_domain
		if check_domain('saas') and self.business:
			if self.business:
				abbr=frappe.db.get_value('Business',self.business,'abbr')
				naming_series='PAY-.YYYY.-'
				if abbr:
					naming_series+=abbr+'-'
				self.naming_series=naming_series
				from frappe.model.naming import make_autoname
				self.name = make_autoname(naming_series+'.#####', doc=self)

	def validate(self):
		if self.paid_amount: 
			for d in self.get("references"):
				if flt(self.paid_amount)>flt(d.total_amount):
					frappe.throw("Amount is greater than allocated total amount!")
				remain=flt(d.total_amount)-flt(self.paid_amount)
				d.outstanding_amount=remain
				d.allocated_amount=self.paid_amount
				if d.reference_doctype == 'Order':
					outstanding = frappe.db.get_value('Order', d.reference_name, 'outstanding_amount')
					if flt(outstanding) < flt(d.allocated_amount):
						frappe.throw(frappe._('Amount is greater than the outstanding amount'))

	def on_update(self):
		if self.party_type and self.party:
			selected_field=frappe.db.get_all('Party Name List',fields=['party_name_field'],filters={'parent':'Party Settings','party_type':self.party_type})
			if selected_field:
				res=frappe.db.get_value(self.party_type,self.party,selected_field[0].party_name_field)
				self.party_name=res

	def on_submit(self):
		if self.paid_amount: 
			for d in self.get("references"):
				if self.payment_type=="Receive":
					if d.reference_doctype=="Wallet Transaction":
						if frappe.db.get_value(d.reference_doctype,d.reference_name,"is_settlement_paid")==0:
							frappe.db.set_value(d.reference_doctype,d.reference_name,"is_settlement_paid",1)
							frappe.db.commit()
					# frappe.db.set_value(d.reference_doctype,d.reference_name,"outstanding_amount",d.outstanding_amount)
					# if flt(d.total_amount)==flt(d.allocated_amount) and frappe.db.get_value("DocField", {"parent": d.reference_doctype,"fieldname": "payment_status"}):
					# 	frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Paid")
					# else:
					# 	if frappe.db.get_value("DocField", {"parent": d.reference_doctype,"fieldname": "payment_status"}):
					# 		frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Partially Paid")
					payment = frappe.get_doc(d.reference_doctype, d.reference_name)
					payment.outstanding_amount = d.outstanding_amount
					if d.reference_doctype=="Sales Invoice":
						# paid= frappe.db.get_value("Sales Invoice",d.reference_name,"paid_amount")
						# balance= frappe.db.get_value("Sales Invoice",d.reference_name,"outstanding_amount")
						if flt(d.total_amount)==flt(d.allocated_amount):
							#created by sivaranjani
							from ecommerce_business_store.accounts.api import update_docstatus
							update_docstatus(d.reference_doctype, d.reference_name, "status","Paid")
					
					if flt(d.total_amount)==flt(d.allocated_amount) and frappe.db.get_value("DocField", {"parent": d.reference_doctype,"fieldname": "payment_status"}):
						payment.payment_status = "Paid"
					else:
						if frappe.db.get_value("DocField", {"parent": d.reference_doctype,"fieldname": "payment_status"}):
							payment.payment_status = "Partially Paid" 
					#updated by kartheek
					try:
						payment.save(ignore_permissions=True)
					except Exception:
						if d.reference_doctype == "Order":
							frappe.db.sql('''UPDATE `tabOrder` SET outstanding_amount = %(outstanding_amount)s , 
							  payment_status= %(payment_status)s WHERE name = %(doc_name)s''',
							  {"payment_status":payment.payment_status, "doc_name":d.reference_name, "outstanding_amount": d.outstanding_amount})
							
							frappe.db.commit()
					#updated by kartheek

				if self.payment_type=="Pay":
					if frappe.db.get_value("Purchase Invoice",d.reference_name,"name"):
						frappe.db.set_value("Purchase Invoice",d.reference_name,"outstanding_amount",d.outstanding_amount)
					if d.reference_doctype == 'Order':
						if flt(d.outstanding_amount) == flt(0):
							amount = 0
						else:
							amount = d.outstanding_amount * -1
						# frappe.db.set_value(d.reference_doctype,d.reference_name,"outstanding_amount", amount)
						# if flt(d.total_amount)==flt(d.allocated_amount):
						# 	frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Paid")
						# else:
						# 	frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Partially Paid")
						payment = frappe.get_doc(d.reference_doctype, d.reference_name)
						payment.outstanding_amount = amount
						# frappe.db.set_value(d.reference_doctype,d.reference_name,"outstanding_amount", amount)
						if flt(d.total_amount)==flt(d.allocated_amount):
							payment.payment_status = "Refunded"
						# 	frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Paid")
						else:
							payment.payment_status = "Partially Refunded"
						# 	frappe.db.set_value(d.reference_doctype,d.reference_name,"payment_status","Partially Paid")
						
						#updated by kartheek
						try:
							payment.save(ignore_permissions=True)
						except Exception:
							frappe.log_error(frappe.get_traceback(), "accounts.payment_entry.on_submit")
							if d.reference_doctype == "Order":
								frappe.db.sql(''' UPDATE `tabOrder` SET outstanding_amount = %(outstanding_amount)s , 
												  payment_status= %(payment_status)s WHERE name = %(doc_name)s''',{"payment_status":payment.payment_status,
												  										 "outstanding_amount":d.outstanding_amount,
												  										 
												  										 "doc_name":d.reference_name})
								frappe.db.commit()
					   #updated by kartheek
				slt = []
				if self.payment_type:
					slt = frappe.db.sql("""select r.* from `tabPayment Entry` p inner join `tabPayment Reference` r on p.name=r.parent where r.reference_name=%s and p.payment_type=%s and p.party=%s and r.reference_doctype=%s and p.docstatus=1 and p.name <> %s""",(d.reference_name,self.payment_type,self.party,d.reference_doctype,self.name),as_dict=True)
				# if slt:
				total=(d.allocated_amount or 0)
				for refs in slt:
					if refs["allocated_amount"]:
						total +=flt(refs["allocated_amount"])
				if self.payment_type=="Receive":
					if d.reference_doctype != 'Membership Payment':
						frappe.db.set_value(d.reference_doctype,d.reference_name,"paid_amount",total)
					else:
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'paid', 1)

				if self.payment_type=="Pay":
					if d.reference_doctype=="Purchase Invoice":
						frappe.db.set_value("Purchase Invoice",d.reference_name,"paid_amount",total)
						paid= frappe.db.get_value("Purchase Invoice",d.reference_name,"paid_amount")
						grand= frappe.db.get_value("Purchase Invoice",d.reference_name,"grand_total")
						frappe.db.commit()
						if flt(paid)==flt(grand):
							frappe.db.set_value("Purchase Invoice",d.reference_name,"status","Paid")
						else:
							frappe.db.set_value("Purchase Invoice",d.reference_name,"status","Partially Paid")
						frappe.db.commit()
					if d.reference_doctype=="Invoice":
						frappe.db.set_value("Invoice",d.reference_name,"paid_amount",total)
						paid= frappe.db.get_value("Invoice",d.reference_name,"paid_amount")
						grand= frappe.db.get_value("Invoice",d.reference_name,"grand_total")
						if flt(paid)==flt(grand):
							frappe.db.set_value("Invoice",d.reference_name,"status","Paid")
						frappe.db.commit()
					if d.reference_doctype == 'Expense Entry':
						outstanding = 0
						if d.allocated_amount == d.total_amount:
							outstanding = 0
						else:
							outstanding = d.total_amount - d.allocated_amount
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'outstanding_amount', outstanding)
						frappe.db.commit()

		# self.make_gl_entries()

	def on_cancel(self):
		if self.paid_amount: 
			for d in self.get("references"):
				# if d.reference_doctype=="Wallet Transaction":
				# 	doc = frappe.get_doc("Wallet Transaction",d.reference_name)
				# 	doc.docstatus = 2
				# 	doc.save(ignore_permissions=True)
				if self.payment_type=="Receive" and d.reference_doctype not in ["Wallet Transaction", "Membership Payment"]:
					outstand_before=frappe.db.get_value(d.reference_doctype,d.reference_name,"outstanding_amount")
					paid_before=frappe.db.get_value(d.reference_doctype,d.reference_name,"paid_amount")
					outstand_after=flt(outstand_before)+flt(self.paid_amount)
					paid_after=flt(paid_before)-flt(self.paid_amount)
					frappe.db.set_value(d.reference_doctype,d.reference_name,"outstanding_amount",outstand_after)
					frappe.db.set_value(d.reference_doctype,d.reference_name,"paid_amount",paid_after)
					frappe.db.commit()
					if paid_after == 0:
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'payment_status', 'Pending')
					else:
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'payment_status', 'Partially Paid')
					slt=frappe.db.sql("select * from `tabPayment Reference` where reference_name=%s ",(d.reference_name),as_dict=True)
				if self.payment_type=="Pay" and d.reference_doctype == "Purchase Invoice":
					outstand_before=frappe.db.get_value("Purchase Invoice",d.reference_name,"outstanding_amount")
					paid_before=frappe.db.get_value("Purchase Invoice",d.reference_name,"paid_amount")
					outstand_after=flt(outstand_before)+flt(self.paid_amount)
					paid_after=flt(paid_before)-flt(self.paid_amount)
					frappe.db.set_value("Purchase Invoice",d.reference_name,"outstanding_amount",outstand_after)
					frappe.db.set_value("Purchase Invoice",d.reference_name,"paid_amount",paid_after)
					frappe.db.commit()
					slt=frappe.db.sql("select * from `tabPayment Reference` where reference_name=%s ",(d.reference_name),as_dict=True)
				if self.payment_type == 'Pay' and d.reference_doctype == 'Expense Entry':
					if d.total_amount == d.allocated_amount:
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'outstanding_amount', d.allocated_amount)
					else:
						outstanding = frappe.db.get_value(d.reference_doctype, d.reference_name, 'outstanding_amount')
						outstanding = outstanding + doc.allocated_amount
						frappe.db.set_value(d.reference_doctype, d.reference_name, 'outstanding_amount', outstanding)
					frappe.db.commit()
				if self.payment_type == 'Receive' and d.reference_doctype == 'Membership Payment':
					frappe.db.set_value(d.reference_doctype, d.reference_name, 'paid', 0)
					frappe.db.commit()
		# cancel_gl_entries('Payment Entry', self.name)
			
	def on_trash(self):
		pass

	# def make_gl_entries(self):
	# 	business = None
	# 	if check_domain('single_vendor') or check_domain('saas'):
	# 		check_type = next((x for x in self.references if x.reference_doctype == 'Order'), None)
	# 		if check_type:
	# 			business = frappe.db.get_value(check_type.reference_doctype, check_type.reference_name, 'business')
	# 			if not business:
	# 				doc = frappe.get_doc(check_type.reference_doctype, check_type.reference_name)
	# 				if doc.order_item:
	# 					business = doc.order_item[0].business
	# 			make_accounting_entry('Payment Entry', self.name, business=business)

@frappe.whitelist()
def get_reference_details(reference_doctype, reference_name, party_account_currency):
	total_amount = outstanding_amount = exchange_rate = None
	ref_doc = frappe.get_doc(reference_doctype, reference_name)
	company_currency = "USD" 

	if reference_doctype == "Invoice":
		if party_account_currency == company_currency:
			if ref_doc.doctype == "Expense Claim":
				total_amount = ref_doc.total_sanctioned_amount
			elif ref_doc.doctype == "Employee Advance":
				total_amount = ref_doc.advance_amount
			else:
				total_amount = ref_doc.base_grand_total
			exchange_rate = 1
		else:
			total_amount = ref_doc.grand_total

			# Get the exchange rate from the original ref doc
			# or get it based on the posting date of the ref doc
			# exchange_rate = ref_doc.get("conversion_rate") or \
			# 	get_exchange_rate(party_account_currency, company_currency, ref_doc.posting_date)
			exchange_rate=1
		if reference_doctype in ("Invoice"):
			outstanding_amount = ref_doc.get("outstanding_amount")
		# elif reference_doctype == "Expense Claim":
		# 	outstanding_amount = flt(ref_doc.get("total_sanctioned_amount")) \
		# 		- flt(ref_doc.get("total_amount+reimbursed")) - flt(ref_doc.get("total_advance_amount"))
		# elif reference_doctype == "Employee Advance":
		# 	outstanding_amount = ref_doc.advance_amount - flt(ref_doc.paid_amount)
		else:
			outstanding_amount = flt(total_amount) - flt(ref_doc.advance_paid)
	else:
		# Get the exchange rate based on the posting date of the ref doc
		exchange_rate = get_exchange_rate(party_account_currency,
			company_currency, ref_doc.posting_date)

	return frappe._dict({
		"due_date": ref_doc.get("due_date"),
		"total_amount": total_amount,
		"outstanding_amount": outstanding_amount,
		"exchange_rate": exchange_rate
	})

