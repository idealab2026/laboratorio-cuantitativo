#!/usr/bin/env python3
"""Build institutional MIDAS PDFs from the exact public, dated thesis catalog.

No market data, private Drive links, alternate valuations or interim reports are
created here. Both the web report and the PDF consume the same two JSON files.
"""
import argparse
from html import escape
import json
import math
from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String, Line

TICKER=re.compile(r'^[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?$')
BAD_SOURCE=re.compile(r'https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\bpersonal_[a-z0-9_]+', re.I)
NAVY=colors.HexColor("#102b4e")
GOLD=colors.HexColor("#a9884f")
EDGE=colors.HexColor("#d9e2ec")
MUTED=colors.HexColor("#657c92")
PALE=colors.HexColor("#f5f8fb")
FONT="Helvetica"
FONT_BOLD="Helvetica-Bold"

def init_fonts():
    global FONT,FONT_BOLD
    candidates=[
      ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
      ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
       "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for regular,bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("MidasRegular",regular))
            pdfmetrics.registerFont(TTFont("MidasBold",bold))
            FONT,FONT_BOLD="MidasRegular","MidasBold"
            return

def numeric(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def amount(x,cc="USD"):
    if not numeric(x):return "N/D"
    return f"{x:,.2f}".replace(",","¤").replace(".",",").replace("¤",".")+" "+cc
def percent(x):
    if not numeric(x):return "N/D"
    return ("+" if x>0 else "")+f"{x:.2f}".replace(".",",")+" %"
def P(text,style):
    return Paragraph(escape(str(text if text is not None else "N/D")).replace("\n","<br/>"),style)
def verify(theses,reports):
    records=theses.get("records",[])
    if len(records)!=25 or len({r.get("ticker") for r in records})!=25:
        raise ValueError("Public thesis catalog must contain 25 unique records")
    if reports.get("schema")!="midas_canonical_web_reports_v1" or not isinstance(reports.get("reports"),list):
        raise ValueError("Canonical report manifest invalid")
    tickers={r["ticker"] for r in records}
    by_ticker={}
    for item in reports["reports"]:
        t=item.get("ticker","")
        source=item.get("source_text","")
        if t not in tickers or not TICKER.fullmatch(t) or t in by_ticker or item.get("publication_gate")!="approved" or not isinstance(source,str) or len(source)<500 or len(source)>180000 or BAD_SOURCE.search(source):
            raise ValueError("Unreviewed or unsafe canonical report: "+t)
        by_ticker[t]=item
    return records,by_ticker

def chart(record):
    cases=[("BAJISTA","bearTarget","#a35a69"),("CENTRAL","baseTarget","#183c67"),("ALCISTA","bullTarget","#2b887e")]
    vals=[record.get(key) for _,key,_ in cases if numeric(record.get(key)) and record[key]>=0]
    if not vals:return None
    reference=record.get("referencePrice")
    mx=max(vals+[reference if numeric(reference) else 0,1])*1.15
    out=Drawing(485,188)
    for i,(label,key,color) in enumerate(cases):
        y=138-i*49
        out.add(String(4,y+6,label,fontName=FONT_BOLD,fontSize=9,fillColor=NAVY))
        value=record.get(key)
        if numeric(value) and value>=0:
            width=max(2, value/mx*310)
            out.add(Rect(95,y-2,width,23,fillColor=colors.HexColor(color),strokeColor=None,rx=4,ry=4))
            out.add(String(min(98+width+5,400),y+5,amount(value,record.get("currency","USD")),fontName=FONT,fontSize=8,fillColor=NAVY))
        else:
            out.add(String(95,y+5,"N/D",fontName=FONT,fontSize=8,fillColor=NAVY))
    if numeric(reference):
        x=95+reference/mx*310
        out.add(Line(x,23,x,174,strokeColor=GOLD,strokeWidth=1,strokeDashArray=[4,3]))
        out.add(String(95,3,"Referencia histórica: "+amount(reference,record.get("currency","USD")),fontName=FONT,fontSize=8,fillColor=GOLD))
    return out

def styles():
    base=getSampleStyleSheet()
    return {
      "brand":ParagraphStyle("MidasBrand",parent=base["Normal"],fontName=FONT_BOLD,fontSize=9,leading=13,textColor=GOLD,spaceAfter=15),
      "title":ParagraphStyle("MidasTitle",parent=base["Title"],fontName=FONT_BOLD,fontSize=22,leading=28,textColor=NAVY,alignment=TA_LEFT,spaceAfter=8),
      "subtitle":ParagraphStyle("MidasSub",parent=base["Normal"],fontName=FONT,fontSize=8,leading=13,textColor=MUTED,spaceAfter=15),
      "heading":ParagraphStyle("MidasHeading",parent=base["Heading2"],fontName=FONT_BOLD,fontSize=14,leading=19,textColor=NAVY,spaceBefore=16,spaceAfter=10,keepWithNext=True),
      "minor":ParagraphStyle("MidasMinor",parent=base["Heading3"],fontName=FONT_BOLD,fontSize=10,leading=15,textColor=NAVY,spaceBefore=14,spaceAfter=6,keepWithNext=True),
      "text":ParagraphStyle("MidasText",parent=base["BodyText"],fontName=FONT,fontSize=8.6,leading=14,textColor=NAVY,spaceAfter=8,splitLongWords=True),
      "small":ParagraphStyle("MidasSmall",parent=base["Normal"],fontName=FONT,fontSize=7.3,leading=11,textColor=MUTED,spaceAfter=8,splitLongWords=True),
      "meta":ParagraphStyle("MidasMeta",parent=base["Normal"],fontName=FONT_BOLD,fontSize=7.1,leading=10,textColor=MUTED),
      "metric":ParagraphStyle("MidasMetric",parent=base["Normal"],fontName=FONT_BOLD,fontSize=10,leading=15,textColor=NAVY,splitLongWords=True),
    }

def report_pdf(record, extra, target):
    init_fonts()
    s=styles()
    cc=record.get("currency") or "USD"
    def footer(c,doc):
        c.saveState()
        c.setStrokeColor(EDGE);c.line(18*mm,16*mm,A4[0]-18*mm,16*mm)
        c.setFont(FONT,7);c.setFillColor(MUTED)
        c.drawString(18*mm,12*mm,"IDEA LAB / MIDAS · Estudio histórico · No constituye asesoramiento financiero")
        c.drawRightString(A4[0]-18*mm,12*mm,str(doc.page))
        c.restoreState()
    doc=SimpleDocTemplate(str(target),pagesize=A4,
        leftMargin=18*mm,rightMargin=18*mm,topMargin=20*mm,bottomMargin=19*mm,
        title="MIDAS · "+record["ticker"]+" · Informe de inversión",
        author="IDEA LAB · MIDAS")
    story=[]
    def para(text,sty="text"):story.append(P(text,s[sty]))
    def heading(text):para(text,"heading")
    para("IDEA LAB   /   MIDAS   ·   INVESTMENT RESEARCH FY2031","brand")
    para(record.get("company",record["ticker"])+"  ·  "+record["ticker"],"title")
    name=extra.get("version","Ficha documental · edición histórica") if extra else "Ficha documental · edición histórica"
    para(record.get("market","Mercado pendiente")+"  |  "+name+"  |  Corte "+(extra or {}).get("document_date",record.get("studyDate","N/D")),"subtitle")
    kpis=[
      ("DICTAMEN",(extra or {}).get("verdict") or record.get("thesisStatus","Pendiente")),
      ("REFERENCIA HISTÓRICA",amount(record.get("referencePrice"),cc)),
      ("OBJETIVO CENTRAL FY2031",amount(record.get("baseTarget"),cc)),
      ("CAGR CENTRAL",percent(record.get("baseCagr"))),
      ("ENTRADA PARA 15 %",amount(record.get("priceFor15"),cc)),
      ("ÚLTIMA REVISIÓN",record.get("lastReview","N/D")),
    ]
    panels=[]
    for label,value in kpis:
        val=str(value)
        if len(val)>58:val=val[:55]+"…"
        panels.append([P(label,s["meta"]),P(val,s["metric"])])
    table=Table([[panels[0],panels[1],panels[2]],[panels[3],panels[4],panels[5]]],
                colWidths=[57*mm]*3,rowHeights=[29*mm,29*mm])
    table.setStyle(TableStyle([
      ("BACKGROUND",(0,0),(-1,-1),PALE),("GRID",(0,0),(-1,-1),.5,EDGE),
      ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),11),
      ("RIGHTPADDING",(0,0),(-1,-1),7)
    ]))
    story.append(table);story.append(Spacer(1,12))
    heading("1. Resumen para el comité")
    para(record.get("summary") or "No documentado en el expediente")
    heading("2. Negocio y ventajas competitivas")
    para((extra or {}).get("business") or record.get("summary") or "No documentado")
    heading("3. Hipótesis y catalizadores")
    para((extra or {}).get("drivers") or record.get("drivers") or "No documentado")
    heading("4. Valoración y escenarios")
    drawing=chart(record)
    if drawing:story.append(drawing)
    rows=[[P(k,s["meta"]) for k in ["ESCENARIO","PRECIO OBJETIVO FY2031","CAGR HISTÓRICO"]]]
    for title,price,cagr in [("Bajista","bearTarget","bearCagr"),("Central","baseTarget","baseCagr"),("Alcista","bullTarget","bullCagr")]:
        rows.append([P(title,s["text"]),P(amount(record.get(price),cc),s["text"]),P(percent(record.get(cagr)),s["text"])])
    t=Table(rows,colWidths=[51*mm,65*mm,55*mm],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),PALE),("LINEBELOW",(0,0),(-1,-1),.5,EDGE),
      ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(t)
    para("Umbrales de entrada quinquenales derivados del escenario central; solo el 15 % procede del expediente si consta.","small")
    for rate in (.10,.12,.15,.20):
        own=rate==.15 and numeric(record.get("priceFor15"))
        v=record["priceFor15"] if own else (record.get("baseTarget")/((1+rate)**5) if numeric(record.get("baseTarget")) else None)
        para(str(int(rate*100))+" % anual: "+amount(v,cc)+(" · Expediente original" if own else " · Cálculo indicativo"),"small")
    heading("5. Riesgos e invalidación")
    para((extra or {}).get("risks") or record.get("risks") or "No documentado")
    heading("6. Resultados y seguimiento")
    para(record.get("earningsRecord") or "Sin fechas documentales verificadas")
    heading("7. Investigación íntegra" if extra else "7. Estado documental")
    source=(extra or {}).get("source_text","")
    if source:
        for block in re.split(r"\n\s*\n",source.replace("\r","")):
            block=block.strip()
            if not block:continue
            if len(block)<125 and (re.match(r"^\d{1,2}[.)]\s",block) or (block.isupper() and len(block)>10)):
                para(block,"minor")
            else:
                for start in range(0,len(block),1800):
                    para(block[start:start+1800])
    else:
        para("No se ha aprobado todavía un informe ejecutivo íntegro para esta compañía. La ficha recoge solo los datos del expediente histórico.","small")
    heading("8. Conclusión de inversión")
    para("Estado de la tesis: "+str(record.get("thesisStatus") or "Pendiente"))
    para("Estado de la valoración: "+str(record.get("valuationStatus") or "Pendiente"))
    para("Fecha de referencia: "+str(record.get("studyDate") or "N/D")+"; los escenarios no son cotizaciones actuales.","small")
    target.parent.mkdir(parents=True,exist_ok=True)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    if target.stat().st_size<2000:raise RuntimeError("PDF vacío o inválido: "+str(target))

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--theses",required=True)
    arg.add_argument("--reports",required=True)
    arg.add_argument("--output",required=True)
    opt=arg.parse_args()
    records,reports=verify(json.loads(Path(opt.theses).read_text("utf8")),
        json.loads(Path(opt.reports).read_text("utf8")))
    output=Path(opt.output);output.mkdir(parents=True,exist_ok=True)
    for record in records:report_pdf(record,reports.get(record["ticker"]),output/(record["ticker"]+".pdf"))
    pdfs=list(output.glob("*.pdf"))
    if len(pdfs)!=25:raise RuntimeError("Se esperaban 25 PDFs; obtenidos "+str(len(pdfs)))
    print("OK:",len(pdfs),"PDFs reproducibles desde el catálogo MIDAS")

if __name__=="__main__":main()
