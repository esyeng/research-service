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

date = datetime.now().date()


PDF_FILENAME = f"job-market-status-report__{date}.pdf"
EMAIL_PASS = require_env("EMAIL_PASS")
EMAIL_USER = require_env("EMAIL_USER")
NAME_USER = require_env("NAME_USER")
NAME_TO = require_env("NAME_TO")
EMAIL_TO = require_env("EMAIL_TO")
    
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

    essay = extract_xml(report, 'essay')
    sources = extract_xml(report, 'sources')
    
    full_string = f"{essay}\n\n{sources}"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y_position = height - 50
    line_height = 14
    margin = 50

    paragraphs = full_string.split('\n\n')
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

    with open(PDF_FILENAME, 'wb') as f:
        f.write(buffer.getvalue())

    return PDF_FILENAME


async def run_and_write():
    orchestrator = ResearchOrchestrator(4, market_report_prompt) # report writer instance
    print(PDF_FILENAME)
    try:
        result = await orchestrator.execute_research_sync(market_report_query, n_tasks=4, max_searches=5)
    
        if result:
            pdf = report_to_pdf(result)
            if pdf:
                print('created pdf')
                return True
            print(result)
            return result
    except Exception as e:
        print(f"error running researcher on job-report, {e}")
    

async def main():
    out = await run_and_write()
    if out == True:
        try:
            compose_mail(
                subject="Weekly Job Market Report",
                frm=EMAIL_USER,
                to=EMAIL_TO,
                cc="yenigun13@gmail.com",
                text="Hey me!\n\nHere's that weekly job market report you asked for 😊\n\nI hope your day goes well, keep up the good work!\n\nYou're doing great.\nI love you :)\n\nWarmly,\n{NAME_USER}\n\n",
                files=[PDF_FILENAME],
                has_attachment=True
            )
        except Exception as e:
            print(f"Error occurred: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())