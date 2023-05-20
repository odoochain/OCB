--
-- PostgreSQL database dump
--

-- Dumped from database version 14.5
-- Dumped by pg_dump version 14.2

-- Started on 2023-01-24 01:51:30

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE qu16;
--
-- TOC entry 4887 (class 1262 OID 144569)
-- Name: qu16; Type: DATABASE; Schema: -; Owner: odoo
--

CREATE DATABASE qu16 WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'zh_CN.UTF-8';


ALTER DATABASE qu16 OWNER TO odoo;

\connect qu16

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 659 (class 1259 OID 150969)
-- Name: account_account; Type: TABLE; Schema: public; Owner: odoo
--

CREATE TABLE public.account_account (
    id integer NOT NULL,
    message_main_attachment_id integer,
    currency_id integer,
    company_id integer NOT NULL,
    group_id integer,
    root_id integer,
    create_uid integer,
    write_uid integer,
    name character varying NOT NULL,
    code character varying(64) NOT NULL,
    account_type character varying NOT NULL,
    internal_group character varying,
    note text,
    deprecated boolean,
    include_initial_balance boolean,
    reconcile boolean,
    is_off_balance boolean,
    non_trade boolean,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    asset_model integer,
    create_asset character varying NOT NULL,
    multiple_assets_per_line boolean
);


ALTER TABLE public.account_account OWNER TO odoo;

--
-- TOC entry 4888 (class 0 OID 0)
-- Dependencies: 659
-- Name: TABLE account_account; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON TABLE public.account_account IS 'Account';


--
-- TOC entry 4889 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.message_main_attachment_id; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.message_main_attachment_id IS 'Main Attachment';


--
-- TOC entry 4890 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.currency_id; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.currency_id IS 'Account Currency';


--
-- TOC entry 4891 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.company_id; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.company_id IS 'Company';


--
-- TOC entry 4892 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.group_id; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.group_id IS 'Group';


--
-- TOC entry 4893 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.root_id; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.root_id IS 'Root';


--
-- TOC entry 4894 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.create_uid; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.create_uid IS 'Created by';


--
-- TOC entry 4895 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.write_uid; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.write_uid IS 'Last Updated by';


--
-- TOC entry 4896 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.name; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.name IS 'Account Name';


--
-- TOC entry 4897 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.code; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.code IS 'Code';


--
-- TOC entry 4898 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.account_type; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.account_type IS 'Type';


--
-- TOC entry 4899 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.internal_group; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.internal_group IS 'Internal Group';


--
-- TOC entry 4900 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.note; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.note IS 'Internal Notes';


--
-- TOC entry 4901 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.deprecated; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.deprecated IS 'Deprecated';


--
-- TOC entry 4902 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.include_initial_balance; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.include_initial_balance IS 'Bring Accounts Balance Forward';


--
-- TOC entry 4903 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.reconcile; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.reconcile IS 'Allow Reconciliation';


--
-- TOC entry 4904 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.is_off_balance; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.is_off_balance IS 'Is Off Balance';


--
-- TOC entry 4905 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.non_trade; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.non_trade IS 'Non Trade';


--
-- TOC entry 4906 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.create_date; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.create_date IS 'Created on';


--
-- TOC entry 4907 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.write_date; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.write_date IS 'Last Updated on';


--
-- TOC entry 4908 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.asset_model; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.asset_model IS 'Asset Model';


--
-- TOC entry 4909 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.create_asset; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.create_asset IS 'Create Asset';


--
-- TOC entry 4910 (class 0 OID 0)
-- Dependencies: 659
-- Name: COLUMN account_account.multiple_assets_per_line; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON COLUMN public.account_account.multiple_assets_per_line IS 'Multiple Assets per Line';


--
-- TOC entry 658 (class 1259 OID 150968)
-- Name: account_account_id_seq; Type: SEQUENCE; Schema: public; Owner: odoo
--

CREATE SEQUENCE public.account_account_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.account_account_id_seq OWNER TO odoo;

--
-- TOC entry 4911 (class 0 OID 0)
-- Dependencies: 658
-- Name: account_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: odoo
--

ALTER SEQUENCE public.account_account_id_seq OWNED BY public.account_account.id;


--
-- TOC entry 4728 (class 2604 OID 150972)
-- Name: account_account id; Type: DEFAULT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account ALTER COLUMN id SET DEFAULT nextval('public.account_account_id_seq'::regclass);


--
-- TOC entry 4881 (class 0 OID 150969)
-- Dependencies: 659
-- Data for Name: account_account; Type: TABLE DATA; Schema: public; Owner: odoo
--

COPY public.account_account (id, message_main_attachment_id, currency_id, company_id, group_id, root_id, create_uid, write_uid, name, code, account_type, internal_group, note, deprecated, include_initial_balance, reconcile, is_off_balance, non_trade, create_date, write_date, asset_model, create_asset, multiple_assets_per_line) FROM stdin;
22	\N	\N	1	\N	52052	1	1	Foreign Exchange Gain	441000	income	income	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
23	\N	\N	1	\N	52052	1	1	Cash Difference Gain	442000	income	income	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
24	\N	\N	1	\N	52053	1	1	Other Income	450000	income_other	income	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
25	\N	\N	1	\N	53048	1	1	Cost of Goods Sold	500000	expense_direct_cost	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
26	\N	\N	1	\N	54048	1	1	Expenses	600000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
27	\N	\N	1	\N	54049	1	1	Purchase of Equipments	611000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
28	\N	\N	1	\N	54049	1	1	Rent	612000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
29	\N	\N	1	\N	54050	1	1	Bank Fees	620000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
30	\N	\N	1	\N	54051	1	1	Salary Expenses	630000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
31	\N	\N	1	\N	54052	1	1	Foreign Exchange Loss	641000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
32	\N	\N	1	\N	54052	1	1	Cash Difference Loss	642000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
33	\N	\N	1	\N	57054	1	1	RD Expenses	961000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
34	\N	\N	1	\N	57054	1	1	Sales Expenses	962000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
35	\N	\N	1	\N	49048	1	1	Account Receivable (PoS)	101300	asset_receivable	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
36	\N	\N	1	\N	52052	1	1	Cash Discount Loss	443000	expense	expense	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
37	\N	\N	1	\N	54052	1	1	Cash Discount Gain	643000	income	income	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
38	\N	\N	1	\N	49048	1	1	Bank Suspense Account	101401	asset_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
39	\N	\N	1	\N	49048	1	1	Outstanding Receipts	101402	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
40	\N	\N	1	\N	49048	1	1	Outstanding Payments	101403	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
41	\N	\N	1	\N	49048	1	1	Cash	101501	asset_cash	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
42	\N	\N	1	\N	49048	1	1	Bank	101404	asset_cash	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
43	\N	\N	1	\N	57057	1	1	未分配利润/损失	999999	equity_unaffected	equity	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
1	\N	\N	1	\N	49048	1	1	流动性转移	101701	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
2	\N	\N	1	\N	49048	1	1	Current Assets	101000	asset_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
3	\N	\N	1	\N	49049	1	1	Stock Valuation	110100	asset_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
4	\N	\N	1	\N	49049	1	1	Stock Interim (Received)	110200	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
5	\N	\N	1	\N	49049	1	1	Stock Interim (Delivered)	110300	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
6	\N	\N	1	\N	49050	1	1	Account Receivable	121000	asset_receivable	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
7	\N	\N	1	\N	49050	1	1	Products to receive	121100	asset_current	asset	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
8	\N	\N	1	\N	49051	1	1	Tax Paid	131000	asset_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
9	\N	\N	1	\N	49051	1	1	Tax Receivable	132000	asset_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
10	\N	\N	1	\N	49052	1	1	Prepayments	141000	asset_prepayments	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
11	\N	\N	1	\N	49053	1	1	Fixed Asset	151000	asset_fixed	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
12	\N	\N	1	\N	49057	1	1	Non-current assets	191000	asset_non_current	asset	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
13	\N	\N	1	\N	50048	1	1	Current Liabilities	201000	liability_current	liability	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
14	\N	\N	1	\N	50049	1	1	Account Payable	211000	liability_payable	liability	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
15	\N	\N	1	\N	50049	1	1	Bills to receive	211100	liability_current	liability	\N	f	t	t	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
16	\N	\N	1	\N	50053	1	1	Tax Received	251000	liability_current	liability	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
17	\N	\N	1	\N	50053	1	1	Tax Payable	252000	liability_current	liability	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
18	\N	\N	1	\N	50057	1	1	Non-current Liabilities	291000	liability_non_current	liability	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
19	\N	\N	1	\N	51048	1	1	Capital	301000	equity	equity	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
20	\N	\N	1	\N	51048	1	1	Dividends	302000	equity	equity	\N	f	t	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
21	\N	\N	1	\N	52048	1	1	Product Sales	400000	income	income	\N	f	f	f	f	f	2022-12-24 05:32:04.291217	2022-12-24 05:32:04.291217	\N	no	\N
\.


--
-- TOC entry 4912 (class 0 OID 0)
-- Dependencies: 658
-- Name: account_account_id_seq; Type: SEQUENCE SET; Schema: public; Owner: odoo
--

SELECT pg_catalog.setval('public.account_account_id_seq', 43, true);


--
-- TOC entry 4730 (class 2606 OID 150996)
-- Name: account_account account_account_code_company_uniq; Type: CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_code_company_uniq UNIQUE (code, company_id);


--
-- TOC entry 4913 (class 0 OID 0)
-- Dependencies: 4730
-- Name: CONSTRAINT account_account_code_company_uniq ON account_account; Type: COMMENT; Schema: public; Owner: odoo
--

COMMENT ON CONSTRAINT account_account_code_company_uniq ON public.account_account IS 'unique (code,company_id)';


--
-- TOC entry 4732 (class 2606 OID 150976)
-- Name: account_account account_account_pkey; Type: CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_pkey PRIMARY KEY (id);


--
-- TOC entry 4733 (class 2606 OID 155851)
-- Name: account_account account_account_asset_model_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_asset_model_fkey FOREIGN KEY (asset_model) REFERENCES public.account_asset(id) ON DELETE SET NULL;


--
-- TOC entry 4734 (class 2606 OID 151869)
-- Name: account_account account_account_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.res_company(id) ON DELETE RESTRICT;


--
-- TOC entry 4735 (class 2606 OID 151879)
-- Name: account_account account_account_create_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- TOC entry 4736 (class 2606 OID 151864)
-- Name: account_account account_account_currency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES public.res_currency(id) ON DELETE SET NULL;


--
-- TOC entry 4737 (class 2606 OID 151874)
-- Name: account_account account_account_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.account_group(id) ON DELETE SET NULL;


--
-- TOC entry 4738 (class 2606 OID 151859)
-- Name: account_account account_account_message_main_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_message_main_attachment_id_fkey FOREIGN KEY (message_main_attachment_id) REFERENCES public.ir_attachment(id) ON DELETE SET NULL;


--
-- TOC entry 4739 (class 2606 OID 151884)
-- Name: account_account account_account_write_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: odoo
--

ALTER TABLE ONLY public.account_account
    ADD CONSTRAINT account_account_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


-- Completed on 2023-01-24 01:51:31

--
-- PostgreSQL database dump complete
--

