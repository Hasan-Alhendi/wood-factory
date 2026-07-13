app_name = "wood_factory"
app_title = "Wood Factory"
app_publisher = "Horizon"
app_description = "Wood factory customizations"
app_email = "eng.mohamad.hasan.alhendi@gmail.com"
app_license = "mit"

before_install = "wood_factory.setup.ensure_factory_roles"
after_install = "wood_factory.setup.ensure_factory_roles"
after_migrate = "wood_factory.setup.ensure_factory_roles"

scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "wood_factory.alerts.evaluate_factory_alerts"
        ]
    }
}

permission_query_conditions = {
    "Factory Order": "wood_factory.security.factory_order_query",
    "Factory Piece": "wood_factory.security.factory_piece_query",
    "Piece Exception": "wood_factory.security.piece_exception_query",
    "Factory Alert Log": "wood_factory.security.factory_alert_query",
}

has_permission = {
    "Factory Order": "wood_factory.security.factory_order_permission",
    "Factory Piece": "wood_factory.security.factory_piece_permission",
    "Piece Exception": "wood_factory.security.piece_exception_permission",
    "Factory Alert Log": "wood_factory.security.factory_alert_permission",
    "Factory Cost Ledger": "wood_factory.security.financial_document_permission",
    "Factory Piece Stage Cost": "wood_factory.security.financial_document_permission",
    "Factory Accounting Settings": "wood_factory.security.financial_document_permission",
    "Factory Worker Cost Rate": "wood_factory.security.financial_document_permission",
}

doc_events = {
    "Stock Entry": {
        "before_cancel": "wood_factory.accounting.validate_stock_entry_cancel",
        "on_cancel": "wood_factory.accounting.on_stock_entry_cancel",
    }
}
