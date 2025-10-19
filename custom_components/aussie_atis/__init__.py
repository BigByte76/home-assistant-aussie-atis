async def async_setup_entry(hass, entry):
    from .sensor import AussieAtisSensor
    for code in entry.data["airports"]:
        sensor = AussieAtisSensor(hass, code)
        hass.async_create_task(sensor.async_add())
    return True
