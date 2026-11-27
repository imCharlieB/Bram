"""Getting to an options page through BRAM's menus."""
PARENT = {"suggest": "devices", "quick": "devices", "see": "devices", "rooms": "devices",
          "watch_ha": "watching", "watch": "watching", "printers": "watching",
          "comfort": "watching"}


async def go(hass, flow_id, step):
    if step in PARENT:
        await hass.config_entries.options.async_configure(flow_id, {"next_step_id": PARENT[step]})
    return await hass.config_entries.options.async_configure(flow_id, {"next_step_id": step})
