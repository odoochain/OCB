# odoo chain最简安装

my company is immartian2021

python odoo-bin -r odoo -w odoo -d immartian2021 -i base --stop-after-init

    """ Initialize a database with for the ORM.

    This executes base/data/base_data.sql, creates the ir_module_categories
    (taken from each module descriptor file), and creates the ir_module_module
    and ir_model_data entries.

    """

115个表 -》 database
133个初始模块-》 ir_model

http://127.0.0.1:8069/web?#action=35&model=ir.module.module&view_type=kanban&cids=&menu_id=5

选择已安装，可以看到原始安装为8个模块 

安装account,卸载partner_autocomplete，会只有39个models,默认安装了美国科目表

INSERT INTO "public"."res_currency" ("id", "name", "symbol", "rounding", "decimal_places", "active", "position", "currency_unit_label", "currency_subunit_label", "create_uid", "create_date", "write_uid", "write_date") VALUES ('7', 'CNY', '¥', '0.010000', '2', 't', 'before', 'Yuan', 'Fen', '1', '2020-12-12 18:34:54.670355', '1', '2020-12-18 17:37:07.712232');
