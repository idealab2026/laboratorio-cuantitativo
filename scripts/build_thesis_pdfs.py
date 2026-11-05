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
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle

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

def trajectory_chart(record):
    """Geometric interpolation, not a prediction for intermediate fiscal years."""
    ref=record.get("referencePrice")
    pairs=[("Bear","bearTarget","#aa5465"),("Base","baseTarget","#1a4674"),("Bull","bullTarget","#168c7b")]
    filtered=[(name,record.get(key),color) for name,key,color in pairs if numeric(record.get(key)) and record[key]>0]
    if not numeric(ref) or ref<=0 or not filtered:return None
    high=max([ref]+[value for _,value,_ in filtered])*1.14
    dr=Drawing(485,216)
    l,r,b,t=48,445,34,183
    for i in range(5):
        yy=b+(t-b)*i/4
        dr.add(Line(l,yy,r,yy,strokeColor=EDGE,strokeWidth=.6))
        dr.add(String(l-5,yy-2,amount(high*i/4,"").strip(),fontName=FONT,fontSize=6.7,fillColor=MUTED,textAnchor="end"))
    for yr in range(6):
        xx=l+(r-l)*yr/5
        dr.add(String(xx,21,str(2026+yr),fontName=FONT,fontSize=7,fillColor=MUTED,textAnchor="middle"))
    for idx,(name,target,color) in enumerate(filtered):
        points=[]
        for yr in range(6):
            value=ref*((target/ref)**(yr/5))
            xx=l+(r-l)*yr/5
            yy=b+(value/high)*(t-b)
            points.append((xx,yy))
        for (x1,y1),(x2,y2) in zip(points,points[1:]):
            dr.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor(color),strokeWidth=2.3))
        for x,y in points:dr.add(Circle(x,y,2.7,fillColor=colors.HexColor(color),strokeColor=None))
        dr.add(Rect(15+idx*150,196,10,7,fillColor=colors.HexColor(color),strokeColor=None))
        dr.add(String(30+idx*150,195,name+" "+amount(target,record.get("currency") or "USD"),fontName=FONT,fontSize=7.1,fillColor=NAVY))
    return dr

def accumulated_chart(record):
    ref=record.get("referencePrice")
    if not numeric(ref) or ref<=0:return None
    pairs=[("Bear","bearTarget","#aa5465"),("Base","baseTarget","#1a4674"),("Bull","bullTarget","#168c7b")]
    vals=[(name,(record[key]/ref-1)*100,color) for name,key,color in pairs if numeric(record.get(key))]
    if not vals:return None
    lo=min(0,*[v for _,v,_ in vals]);hi=max(0,*[v for _,v,_ in vals])
    dr=Drawing(485,150)
    l,r=105,414
    zero=l+(-lo)/(hi-lo or 1)*(r-l)
    dr.add(Line(zero,10,zero,143,strokeColor=MUTED,strokeWidth=1))
    for i,(name,change,color) in enumerate(vals):
        y=110-i*47
        end=zero+change/(hi-lo or 1)*(r-l)
        dr.add(String(10,y+11,name,fontName=FONT_BOLD,fontSize=9,fillColor=NAVY))
        dr.add(Rect(min(zero,end),y,max(1,abs(end-zero)),22,fillColor=colors.HexColor(color),strokeColor=None,rx=3,ry=3))
        label=percent(change)
        dr.add(String(min(463,max(25,end+7 if change>=0 else end-7)),y+7,label,
                      fontName=FONT_BOLD,fontSize=8,fillColor=NAVY,textAnchor="start" if change>=0 else "end"))
    return dr

def entry_chart(record):
    ref,threshold=record.get("referencePrice"),record.get("priceFor15")
    if not numeric(ref) or ref<=0 or not numeric(threshold) or threshold<=0:return None
    vals=[("Referencia histórica",ref,"#b28d4e"),("Umbral P15",threshold,"#1a4674")]
    base=record.get("baseTarget")
    if numeric(base) and base>0:vals.append(("Base FY2031",base,"#168c7b"))
    mx=max(x for _,x,_ in vals)*1.15
    dr=Drawing(485,150)
    for i,(label,value,color) in enumerate(vals):
        y=109-i*45
        dr.add(String(9,y+8,label,fontName=FONT_BOLD,fontSize=7.8,fillColor=NAVY))
        right=125+270*value/mx
        dr.add(Rect(125,y,270*value/mx,25,fillColor=colors.HexColor(color),strokeColor=None,rx=3,ry=3))
        dr.add(String(min(right+9,460),y+9,amount(value,record.get("currency") or "USD"),
                      fontName=FONT,fontSize=7.8,fillColor=NAVY))
    return dr

def canonical_source_blocks(text):
    """Preserve source order and meaning while repairing flattened text layout."""
    lines=[x.strip().replace("\t"," ") for x in text.replace("\r","").split("\n")]
    heading=re.compile(r"^\d{1,2}(?:\.\d+)?[.)]\s+\D")
    is_figure=re.compile(r"^(?:Figura|Gráfico|Figure|Chart)\s*\d+[.:]",re.I)
    scenario_header=re.compile(r"^(?:FY2031|Indicador|Escenario|Métrica)$",re.I)
    separator=re.compile(r"^[_━─═\-\s]{7,}$")
    bullet=re.compile(r"^(?:[•▪◦]|[-*]\s)\s*")
    tokens=[];i=0
    def is_heading(t):
        return bool(heading.match(t) or re.fullmatch(r"(?:Investment Committee Snapshot|Investment conclusion|Executive summary|Resumen ejecutivo|Conclusión|Riesgos|Catalizadores|Por qué invertir)",t,re.I) or
                (11<len(t)<115 and re.fullmatch(r"[A-ZÁÉÍÓÚÑ0-9\s·:—–/\-()]+",t) and "USD" not in t and len(t.split())<=12))
    while i<len(lines):
        line=lines[i]
        if not line or separator.fullmatch(line):i+=1;continue
        if (scenario_header.fullmatch(line) and i+3<len(lines) and re.search("Bear|Bajista",lines[i+1],re.I)
            and re.search("Base|Central",lines[i+2],re.I) and re.search("Bull|Alcista",lines[i+3],re.I)):
            data=[["Indicador"]+lines[i+1:i+4]];j=i+4
            while j+3<len(lines) and len(data)<17:
                row=lines[j:j+4]
                if not all(row) or len(row[0])>83 or any(len(x)>80 for x in row[1:]) or is_heading(row[0]) or separator.fullmatch(row[0]):break
                data.append(row);j+=4
            if len(data)>=3:tokens.append(("table",data));i=j;continue
        if line=="Parámetro" and i+1<len(lines) and lines[i+1]=="Referencia del informe":
            data=[["Parámetro","Referencia del informe"]];j=i+2
            while j+1<len(lines) and len(data)<25:
                k,v=lines[j:j+2]
                if not k or not v or len(k)>88 or len(v)>180 or is_heading(k) or separator.fullmatch(k):break
                data.append([k,v]);j+=2
            if len(data)>=4:tokens.append(("table",data));i=j;continue
        if is_figure.match(line):tokens.append(("figure",line));i+=1;continue
        if is_heading(line):tokens.append(("heading",line));i+=1;continue
        if bullet.match(line):
            group=[]
            while i<len(lines) and bullet.match(lines[i]):
                group.append(bullet.sub("",lines[i]));i+=1
            tokens.append(("bullets",group));continue
        paragraph=line
        while i+1<len(lines):
            next_line=lines[i+1]
            if (not next_line or is_heading(next_line) or separator.fullmatch(next_line) or is_figure.match(next_line)
                or bullet.match(next_line) or scenario_header.fullmatch(next_line) or next_line=="Parámetro"):break
            if len(paragraph)>145 or paragraph.endswith((".","!","?",":",";","”",'"')):break
            paragraph+=" "+next_line;i+=1
        tokens.append(("paragraph",paragraph));i+=1
    return tokens

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
