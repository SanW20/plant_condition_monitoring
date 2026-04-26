import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from config import EMAIL_SENDER, EMAIL_APP_PASSWORD, EMAIL_RECIPIENT, SMTP_HOST, SMTP_PORT


def send_alert_email(result: dict) -> bool:
    """
    Build and send a consolidated alert email from check_all_plants() result.
    Returns True if sent, False if skipped (no alerts) or failed.
    """
    if not result.get("alerts"):
        return False

    if not EMAIL_SENDER or not EMAIL_APP_PASSWORD or not EMAIL_RECIPIENT:
        print("[email] Email credentials not configured in .env — skipping.")
        return False

    subject, plain_body, html_body = _build_email(result)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"[email] Alert email sent to {EMAIL_RECIPIENT}")
        return True
    except Exception as e:
        print(f"[email] Failed to send email: {e}")
        return False


def _build_email(result: dict) -> tuple[str, str, str]:
    weather = result.get("weather", {})
    alerts_list = result.get("alerts", [])
    ok_list = result.get("ok", [])
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    temp = weather.get("current_temp", "?")
    wind = weather.get("current_wind", "?")
    rain_24 = weather.get("total_rain_24h", 0)

    subject = f"Plant Alert — Tallinn, {now}"

    # ---- Plain text ----
    lines = [
        f"Plant Alert — Tallinn",
        f"Checked: {now}",
        f"",
        f"Current: {temp}°C | Wind: {wind} m/s | Rain 24h: {rain_24:.1f}mm",
        f"",
        "=" * 50,
    ]

    # Group alerts by type for readability
    type_order = [
        "FROST_WARNING",
        "COVER_NEEDED",
        "WIND_RISK",
        "WATER_NEEDED",
        "HEAT_STRESS",
        "HEAVY_RAIN",
    ]
    type_labels = {
        "FROST_WARNING":  "FROST WARNING",
        "COVER_NEEDED":   "COVER NEEDED",
        "WIND_RISK":      "WIND RISK",
        "WATER_NEEDED":   "WATER NEEDED",
        "HEAT_STRESS":    "HEAT STRESS",
        "HEAVY_RAIN":     "HEAVY RAIN",
    }

    # Collect all alerts grouped by type
    by_type: dict[str, list] = {t: [] for t in type_order}
    for entry in alerts_list:
        plant = entry["plant"]
        notes = plant.get("notes", "")
        for alert in entry["alerts"]:
            atype = alert["type"]
            if atype not in by_type:
                by_type[atype] = []
            by_type[atype].append({
                "alert": alert,
                "notes": notes,
            })

    for atype in type_order:
        items = by_type.get(atype, [])
        if not items:
            continue
        lines.append(f"\n{type_labels.get(atype, atype)}")
        for item in items:
            alert = item["alert"]
            notes = item["notes"]
            lines.append(f"  • {alert['message']}")
            if notes:
                lines.append(f"    Note: \"{notes}\"")
            lines.append(f"    -> {alert['action']}")

    if ok_list:
        lines.append(f"\nNo issues detected: {', '.join(ok_list)}")

    plain_body = "\n".join(lines)

    # ---- HTML ----
    level_colours = {"critical": "#c0392b", "warning": "#e67e22"}
    type_icons = {
        "FROST_WARNING": "❄️",
        "COVER_NEEDED":  "🧥",
        "WIND_RISK":     "💨",
        "WATER_NEEDED":  "💧",
        "HEAT_STRESS":   "🌡️",
        "HEAVY_RAIN":    "🌧️",
    }

    html_sections = []
    for atype in type_order:
        items = by_type.get(atype, [])
        if not items:
            continue
        icon = type_icons.get(atype, "")
        label = type_labels.get(atype, atype)
        rows = ""
        for item in items:
            alert = item["alert"]
            notes = item["notes"]
            colour = level_colours.get(alert["level"], "#e67e22")
            rows += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;">
                <strong style="color:{colour};">{alert['message']}</strong><br>
                {"<em style='color:#888;font-size:0.9em;'>Note: &ldquo;" + notes + "&rdquo;</em><br>" if notes else ""}
                <span style="color:#27ae60;">&#8594; {alert['action']}</span>
              </td>
            </tr>"""
        html_sections.append(f"""
        <h3 style="margin:20px 0 6px;color:#2c3e50;">{icon} {label}</h3>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border:1px solid #ddd;border-radius:6px;">
          {rows}
        </table>""")

    ok_html = ""
    if ok_list:
        ok_html = f"""
        <p style="margin-top:20px;color:#27ae60;">
          <strong>No issues:</strong> {', '.join(ok_list)}
        </p>"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;color:#2c3e50;">
      <h2 style="border-bottom:2px solid #27ae60;padding-bottom:8px;">
        Plant Alert &mdash; Tallinn
      </h2>
      <p style="color:#888;font-size:0.9em;">Checked: {now}</p>
      <div style="background:#f8f9fa;padding:12px;border-radius:6px;margin-bottom:16px;">
        <strong>Current conditions:</strong>
        {temp}°C &nbsp;|&nbsp; Wind: {wind} m/s &nbsp;|&nbsp; Rain 24h: {rain_24:.1f}mm
      </div>
      {"".join(html_sections)}
      {ok_html}
      <p style="margin-top:30px;font-size:0.8em;color:#aaa;">
        Samudika Plant Care Assistant &mdash; Tallinn
      </p>
    </body>
    </html>"""

    return subject, plain_body, html_body
