import asyncio
import os
import io
from markdown import markdown
from datetime import datetime
from helpers.smtp import compose_mail
from helpers.data_methods import market_report_prompt, extract_xml
from orchestrator import ResearchOrchestrator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


def get_email_config():
    """Get email configuration when needed instead of at module level"""
    return (
        require_env("EMAIL_USER"),
        require_env("NAME_USER"),
        require_env("NAME_TO"),
        require_env("EMAIL_TO"),
    )


date = datetime.now().date()
PDF_FILENAME = f"job-market-status-report__{date}.pdf"

market_report_query = f"""
Analyze the current job market for software engineers as of {date}. Focus on data and developments from the past 7 days, including:

IMMEDIATE MARKET CONDITIONS (Week of {date}):
- New job postings, hiring announcements, and company recruitment updates from this week
- Current salary ranges and compensation packages being offered this week
- Geographic hotspots and remote work trends observed in recent postings
- Industry sectors showing increased or decreased hiring activity this week

CURRENT EMPLOYER REQUIREMENTS:
- Skills, certifications, and qualifications emphasized in this week's job listings
- Experience levels and educational requirements trending in recent postings
- Technical competencies, software tools, and methodologies mentioned most frequently
- Soft skills and cultural attributes highlighted by employers this week

COMPETITIVE INTELLIGENCE:
- Application-to-interview ratios and hiring timelines observed recently
- Common reasons candidates are being rejected or preferred this week
- Networking opportunities, industry events, and professional development activities happening now
- Salary negotiation trends and successful candidate profiles from recent hires

EMERGING TRENDS AND DISRUPTIONS:
- New technologies, regulations, or industry changes affecting these roles this week
- Companies pivoting their hiring strategies or role definitions recently
- Skills becoming obsolete or newly in-demand based on current job descriptions
- Market disruptions, economic factors, or industry news impacting hiring decisions

TIME-SENSITIVE OPPORTUNITIES:
- Specific companies actively recruiting for these roles this week
- Application deadlines, hiring events, or recruitment drives happening soon
- Seasonal trends or cyclical patterns relevant to current timing
- Professional conferences, certifications, or training programs with immediate enrollment

Please prioritize sources dated within the last 7-14 days and highlight any significant changes from previous weeks or months. Include specific company names, salary figures, location data, and quantitative metrics wherever available."""


def report_to_pdf(report: str):

    essay = extract_xml(report, "essay")
    sources = extract_xml(report, "sources")

    full_string = f"{essay}\n\n{sources}"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y_position = height - 50
    line_height = 14
    margin = 50

    paragraphs = full_string.split("\n\n")
    font_name = "Helvetica"
    font_size = 12
    c.setFont(font_name, font_size)

    for paragraph in paragraphs:
        lines = simpleSplit(paragraph, font_name, font_size, width - 2 * margin)

        for line in lines:
            if y_position < margin:
                c.showPage()
                y_position = height - margin
                c.setFont(font_name, font_size)

            c.drawString(margin, y_position, line)
            y_position -= line_height

        y_position -= line_height / 2

    c.save()
    buffer.seek(0)

    with open(PDF_FILENAME, "wb") as f:
        f.write(buffer.getvalue())

    return PDF_FILENAME


def report_to_html(report: str):
    """Convert report to mobile-friendly HTML with rendered markdown"""
    essay = extract_xml(report, "essay")
    sources = extract_xml(report, "sources")

    # Convert markdown to HTML
    html_content = markdown(f"{essay}\n\n{sources}")

    # Mobile-friendly HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Market Report - {date}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4 {{
            color: #2c3e50;
            margin-top: 1.5em;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
        }}
        pre {{
            background-color: #f8f8f8;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 15px;
            margin-left: 0;
            color: #666;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

    html_filename = f"job-market-status-report__{date}.html"

    with open(html_filename, "w", encoding="utf-8") as f:
        f.write(html_template)

    return html_filename


def report_to_email_html(report: str):
    """Convert report to email-friendly HTML (inline styles, table-based layout)"""
    essay = extract_xml(report, "essay")
    sources = extract_xml(report, "sources")
    
    # Convert markdown to HTML
    html_content = markdown(f"{essay}\n\n{sources}")
    
    # Email-friendly HTML with inline styles (tables for better email client support)
    email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.4; color: #333333;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td align="center" style="padding: 20px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px;">
                    <tr>
                        <td style="padding: 20px; background-color: #ffffff; border: 1px solid #e0e0e0;">
                            {html_content}
                            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                            <p style="font-size: 12px; color: #666666; text-align: center;">
                                Job Market Report generated on {date}
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return email_html



async def run_and_write():
    orchestrator = ResearchOrchestrator(
        4, market_report_prompt
    )  # report writer instance
    print(PDF_FILENAME)
    try:
        result = await orchestrator.execute_research_sync(
            market_report_query, n_tasks=4, max_searches=5
        )

        if result:
            pdf = report_to_pdf(result)
            html = report_to_html(result)
            email_html = report_to_email_html(result)
            if pdf and html:
                print("created pdf and html files")
                return True, email_html
            print(result)
            return result
    except Exception as e:
        print(f"error running researcher on job-report, {e}")




async def main():
    # Get email configuration when the function is called
    EMAIL_USER, NAME_USER, NAME_TO, EMAIL_TO = get_email_config()

    out = await run_and_write()
    if isinstance(out, tuple) and out[0] == True:
        email_html = out[1]
        try:
            compose_mail(
                subject="Weekly Job Market Report",
                frm=EMAIL_USER,
                to=EMAIL_TO,
                cc="yenigun13@gmail.com",
                text=f"Here's this week's report, Esmé! Good luck out there!",
                html=email_html,
                files=[PDF_FILENAME],
                has_attachment=True,
            )
        except Exception as e:
            print(f"Error occurred: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
