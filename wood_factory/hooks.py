app_name = "wood_factory"
app_title = "Wood Factory"
app_publisher = "Horizon"
app_description = "Wood factory customizations"
app_email = "eng.mohamad.hasan.alhendi@gmail.com"
app_license = "mit"

scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "wood_factory.alerts.evaluate_factory_alerts"
        ]
    }
}
