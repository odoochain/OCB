##
https://www.cybrosys.com/odoo/odoo-books/odoo-book-v14/
## api.one

https://github.com/odoo/odoo/commit/407f1f6cdb87a59bbad9f853078d7345cdf9f60c

`api.one` has been deprecated since v9 because it often makes the code
less clear and behaves in ways developers and readers may not expect
since functions decorated with it usually expect a `list` of record(s)
instead of the recordset, whereas most modern Odoo code expects `self`
to be a recordset.

The function `aggregate` was solely being used by `api.one` thus it has
also been removed since there doesn't seem to be any other use for it
thus far.