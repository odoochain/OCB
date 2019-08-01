/**
 * Created by Evelyn ZHONG
 */
odoo.define('stock.picking_validator', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var basicFields = require('web.basic_fields');

    var validator = basicFields.FieldText.extend({
        /**
         * @constructor
         * @override
         */
        init: function(parent, name, record, options) {
            this._super(parent, name, record, options);
            var tx_id = record.data.tx_id
            if(tx_id === 'False'){
                this.do_warn('区块链验证错误！');
            }
        }
    })

    fieldRegistry.add('stock_validator', validator);
})