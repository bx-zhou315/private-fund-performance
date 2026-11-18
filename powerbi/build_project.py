"""Build the portable PBIP report and refresh its browser companion."""
import argparse
import base64
import csv
import gzip
import io
import json
import re
import uuid
from pathlib import Path

from prepare_data import BUILD, PROGRAMMES, SCENARIOS, check_cashflows, check_funds, compare_sql, number

HERE = Path(__file__).resolve().parent
NAME = "CalPERS"
REPORT = HERE / f"{NAME}.Report"
MODEL = HERE / f"{NAME}.SemanticModel"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
MULTIPLE = '0.00"x"'
PERCENT = "0.0%"
USD_BN = '$0.00"bn"'
TEAL, BLUE, INK, MUTED, PAPER = "#007F78", "#425CA4", "#142C3D", "#526579", "#EEF3F6"
DATA_COLOURS = [TEAL, BLUE, "#C16A39", "#697B8F", "#359C96", "#6474AE"]
STATUS = {"within rounding": "Within rounding", "not testable": "No comparable multiple",
          "review difference": "Review difference"}
FUND_LABELS = {
    "Advent International GPE V-D, L.P.": "GPE V-D",
    "Advent International GPE VI-A, L.P.": "GPE VI-A",
    "Advent International GPE VII-C, L.P.": "GPE VII-C",
    "Advent International GPE VIII-B Limited Partnership": "GPE VIII-B",
    "Advent International GPE IX Limited Partnership": "GPE IX",
    "Advent International GPE X Limited Partnership": "GPE X",
    "Ares Senior Direct Lending Fund II": "Ares SDL II",
    "Ares Senior Direct Lending Fund (Delaware) III LP": "Ares SDL III",
}
TYPES = {
    "string": "type text", "int64": "Int64.Type", "double": "type number",
    "boolean": "type logical", "dateTime": "type date",
}


def write_json(path, schema, definition):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"$schema": f"{SCHEMA}/{schema}/schema.json", **definition},
                               indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tmdl_name(value):
    return f"'{value}'" if " " in value else value


def table(name, columns, rows, measures=()):
    """Serialize one typed, credential-free Power Query Import partition."""
    csv_text = io.StringIO(newline="")
    writer = csv.writer(csv_text, lineterminator="\r\n")
    writer.writerow(c[0] for c in columns)
    writer.writerows(rows)
    blob = base64.b64encode(gzip.compress(csv_text.getvalue().encode("utf-8"), mtime=0)).decode()
    chunks = [blob[start:start + 100] for start in range(0, len(blob), 100)]
    lines = [f"table {tmdl_name(name)}"]
    for measure, dax, fmt in measures:
        lines.extend(("", f"\tmeasure '{measure}' = {dax}", f"\t\tformatString: {fmt}"))
    for col, dtype, *options in columns:
        lines.extend(("", f"\tcolumn {tmdl_name(col)}", f"\t\tdataType: {dtype}",
                      f"\t\tsourceColumn: {col}", "\t\tsummarizeBy: none"))
        for prop in options:
            lines.append(f"\t\t{prop}")
    type_pairs = ", ".join(f'{{"{c[0]}", {TYPES[c[1]]}}}' for c in columns)
    lines.extend(("", f"\tpartition {tmdl_name(name)} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
                  "\t\t\t\t    Snapshot = Text.Combine({"))
    lines.extend(f'\t\t\t\t        "{chunk}"{"," if i + 1 < len(chunks) else ""}'
                 for i, chunk in enumerate(chunks))
    lines.extend((
        "\t\t\t\t    }),",
        "\t\t\t\t    Source = Binary.Decompress(Binary.FromText(Snapshot, BinaryEncoding.Base64), Compression.GZip),",
        f'\t\t\t\t    Parsed = Csv.Document(Source, [Delimiter=",", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "\t\t\t\t    Header = Table.PromoteHeaders(Parsed, [PromoteAllScalars=true]),",
        "\t\t\t\t    Nulls = Table.ReplaceValue(Header, \"\", null, Replacer.ReplaceValue, Table.ColumnNames(Header)),",
        f'\t\t\t\t    Typed = Table.TransformColumnTypes(Nulls, {{{type_pairs}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    Typed", "",
    ))
    path = MODEL / "definition" / "tables" / f"{name}.tmdl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def fraction(raw):
    return float(raw) / 100 if raw else None


def make_model(funds, cashflows, results):
    years = sorted({int(f["vintage"]) for f in funds})
    table("Programme", [("Programme Key", "string", "isHidden"), ("Programme", "string")], PROGRAMMES.items())
    table("Vintage", [("Vintage", "int64", "formatString: 0")], [(year,) for year in years])
    table("Manager", [("Manager", "string")], [(manager,) for manager in sorted({f["manager"] for f in funds if f["manager"]})])
    int_col = lambda title: (title, "int64", "formatString: #,0")
    multiple_col = lambda title: (title, "double", f"formatString: {MULTIPLE}")
    decimal_col = lambda title: (title, "double", "formatString: 0.00")
    hidden = ("Programme Key", "string", "isHidden")
    pct_col = lambda title: (title, "double", f"formatString: {PERCENT}")
    keys = [
        "program", "source_row", "fund", "vintage", "commitment", "paid_in", "distributions", "nav",
        "dpi", "rvpi", "tvpi", "reported_multiple",
    ]
    table("Funds", [
        hidden, int_col("Source Row"), ("Fund", "string"), ("Vintage", "int64", "formatString: 0"),
        int_col("Committed USD"), int_col("Paid In USD"), int_col("Distributions USD"), int_col("NAV USD"),
        multiple_col("DPI"), multiple_col("RVPI"), multiple_col("TVPI"), multiple_col("Reported Multiple"),
        pct_col("Source IRR"), ("Multiple Check", "string"), ("Early Life", "boolean"), ("IRR Review", "boolean"),
        ("Source URL", "string", "isHidden"),
    ], [
        [f[k] for k in keys] + [fraction(f["reported_irr_pct"]), STATUS[f["multiple_check"]],
                                f["early_life_flag"].lower(), f["irr_multiple_inconsistent"].lower(), f["source_url"]]
        for f in funds
    ], [
        ("Fund Count", "COUNTROWS ( Funds )", "#,0"),
        ("Paid In", "DIVIDE ( SUM ( Funds[Paid In USD] ), 1000000000 )", USD_BN),
        ("Residual NAV", "DIVIDE ( SUM ( Funds[NAV USD] ), 1000000000 )", USD_BN),
        ("IRR Flags", "CALCULATE ( [Fund Count], KEEPFILTERS ( Funds[IRR Review] = TRUE() ) )", "#,0"),
        ("Median DPI", "MEDIAN ( Funds[DPI] )", MULTIPLE),
        ("Median TVPI", "MEDIAN ( Funds[TVPI] )", MULTIPLE),
        ("DPI Observations", "COUNT ( Funds[DPI] ) + 0", "#,0"),
        ("TVPI Observations", "COUNT ( Funds[TVPI] ) + 0", "#,0"),
        ("IRR Available", "CALCULATE ( COUNT ( Funds[Source IRR] ), KEEPFILTERS ( Funds[IRR Review] = FALSE() ) )", "#,0"),
        ("Multiples Reconciled", 'CALCULATE ( [Fund Count], KEEPFILTERS ( Funds[Multiple Check] = "Within rounding" ) )', "#,0"),
    ])
    case_funds = [f for f in funds if f["manager"]]
    table("Case Funds", [
        hidden, ("Manager", "string", "isHidden"), ("Vintage", "int64", "formatString: 0"),
        ("Fund", "string", "sortByColumn: Vintage"), ("Legal Name", "string"),
        multiple_col("DPI"), multiple_col("RVPI"), multiple_col("TVPI"), pct_col("Realised Share"),
        int_col("Peer n"), multiple_col("Peer Median TVPI"), int_col("Quartile"), ("Review Status", "string"),
    ], [
        [f["program"], f["manager"], f["vintage"], FUND_LABELS[f["fund"]], f["fund"], f["dpi"], f["rvpi"],
         f["tvpi"], f["realised_share"], int(float(f["eligible_cohort_n"])) if f["eligible_cohort_n"] else None,
         f["cohort_median_tvpi"], int(float(f["sample_quartile"])) if f["sample_quartile"] else None,
         "Early life" if f["early_life_flag"] == "True"
         else "Cohort below 8" if not f["sample_quartile"] else "Quartile available"]
        for f in case_funds
    ], [
        ("Case Fund Count", "COUNTROWS ( 'Case Funds' ) + 0", "#,0"),
        ("Distributed Value", "SELECTEDVALUE ( 'Case Funds'[DPI] )", MULTIPLE),
        ("Unrealised Value", "SELECTEDVALUE ( 'Case Funds'[RVPI] )", MULTIPLE),
    ])
    table("Scenario", [
        ("Scenario Key", "string", "isHidden"), ("Scenario Order", "int64", "isHidden"),
        ("Scenario", "string", "sortByColumn: 'Scenario Order'"),
        pct_col("XIRR"), multiple_col("TVPI"), multiple_col("KS PME"),
        pct_col("Direct Alpha"), decimal_col("Funding Trough"), decimal_col("Terminal NAV"),
    ], [
        [key, i, label, result["xirr"], result["tvpi"], result["ks_pme"], result["direct_alpha"],
         result["trough"], result["terminal_nav"]]
        for i, (key, label) in enumerate(SCENARIOS.items()) for result in [results[key]]
    ], [
        ("Base XIRR", 'CALCULATE ( MAX ( Scenario[XIRR] ), REMOVEFILTERS ( Scenario ), Scenario[Scenario Key] = "base" )', "0.00%"),
        ("Delayed XIRR", 'CALCULATE ( MAX ( Scenario[XIRR] ), REMOVEFILTERS ( Scenario ), Scenario[Scenario Key] = "delayed" )', "0.00%"),
        ("XIRR Change", "100 * ( [Delayed XIRR] - [Base XIRR] )", '0.00" pp";-0.00" pp";0.00" pp"'),
        ])
    table("Cash Flow", [
        ("Scenario Key", "string", "isHidden"), ("Quarter End", "dateTime", "formatString: yyyy-MM-dd"),
        decimal_col("Capital Call"), decimal_col("Distribution"), decimal_col("NAV"),
        decimal_col("Net Cash Flow"), decimal_col("Cumulative Net"), decimal_col("Benchmark Level"),
    ], [
        [key] + [row[col] for col in (
            "date", "call", "distribution", "nav", "net_cashflow", "cumulative_net_cashflow", "benchmark_level"
        )]
        for key, rows in cashflows.items() for row in rows
    ], [("Cumulative Net Flow", "SELECTEDVALUE ( 'Cash Flow'[Cumulative Net] )", "0.0")])
    definition = MODEL / "definition"
    write_json(MODEL / "definition.pbism", "item/semanticModel/definitionProperties/1.0.0",
               {"version": "4.2", "settings": {"qnaEnabled": False}})
    (definition / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n\tcompatibilityMode: powerBI\n")
    (definition / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tsourceQueryCulture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        "\tannotation PBI_TimeIntelligenceEnabled = 0\n\n"
        + "\n".join(f"ref table {tmdl_name(name)}" for name in
                    ("Programme", "Vintage", "Manager", "Funds", "Case Funds", "Scenario", "Cash Flow")) + "\n"
    )
    relationships = [
        ("Funds", "Programme Key", "Programme", "Programme Key"),
        ("Funds", "Vintage", "Vintage", "Vintage"),
        ("Case Funds", "Manager", "Manager", "Manager"),
        ("Case Funds", "Programme Key", "Programme", "Programme Key"),
        ("Case Funds", "Vintage", "Vintage", "Vintage"),
        ("Cash Flow", "Scenario Key", "Scenario", "Scenario Key"),
    ]
    (definition / "relationships.tmdl").write_text("\n\n".join(
        f"relationship {uuid.uuid5(uuid.NAMESPACE_URL, 'calpers/' + '/'.join(rel))}\n"
        f"\tfromColumn: {tmdl_name(rel[0])}.{tmdl_name(rel[1])}\n"
        f"\ttoColumn: {tmdl_name(rel[2])}.{tmdl_name(rel[3])}"
        for rel in relationships
    ) + "\n")


def literal(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = f"{value}D"
    return {"expr": {"Literal": {"Value": value}}}


def colour(value):
    return {"solid": {"color": literal(value)}}


def properties(**kwargs):
    return [{"properties": kwargs}]


def field(entity, name, kind="Column"):
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}}


def projection(entity, name, kind="Column", active=False, label=None):
    result = {"field": field(entity, name, kind), "queryRef": f"{entity}.{name}", "nativeQueryRef": name}
    if active:
        result["active"] = True
    if label:
        result["displayName"] = label
    return result


def make_report():
    definition = REPORT / "definition"
    pages = {"portfolio": "Portfolio & Vintage", "manager": "Manager Due Diligence", "cashflow": "Distribution Timing"}
    theme_name = "CalPERS Review"
    write_json(HERE / f"{NAME}.pbip", "pbip/pbipProperties/1.0.0", {
        "version": "1.0", "artifacts": [{"report": {"path": REPORT.name}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(REPORT / "definition.pbir", "item/report/definitionProperties/2.0.0",
               {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{MODEL.name}"}}})
    write_json(definition / "version.json", "item/report/definition/versionMetadata/1.0.0", {"version": "2.0.0"})
    write_json(definition / "report.json", "item/report/definition/report/2.0.0", {
        "themeCollection": {
            "baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55", "type": "SharedResources"},
            "customTheme": {"name": theme_name, "reportVersionAtImport": "5.55", "type": "RegisteredResources"},
        },
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [
            {"name": theme_name, "path": "CalPERSReview.json", "type": "CustomTheme"},
        ]}],
    })
    theme = REPORT / "StaticResources" / "RegisteredResources" / "CalPERSReview.json"
    theme.parent.mkdir(parents=True, exist_ok=True)
    theme.write_text(json.dumps({
        "name": theme_name, "dataColors": DATA_COLOURS, "background": "#FFFFFF", "foreground": INK,
        "tableAccent": TEAL, "good": TEAL, "bad": "#AD442D", "neutral": MUTED,
    }, indent=2) + "\n")
    write_json(definition / "pages" / "pages.json", "item/report/definition/pagesMetadata/1.0.0",
               {"pageOrder": list(pages), "activePageName": "portfolio"})
    for page, label in pages.items():
        write_json(definition / "pages" / page / "page.json", "item/report/definition/page/2.0.0", {
            "name": page, "displayName": label, "displayOption": "FitToPage", "height": 800, "width": 1440,
            "objects": {"background": properties(color=colour(PAPER), transparency=literal(0))},
        })

    order = {page: 0 for page in pages}

    def visual(page, key, visual_type, box, roles=None, *, title=None, objects=None, sort=None):
        name = uuid.uuid5(uuid.NAMESPACE_URL, f"calpers/report/{page}/{key}").hex[:20]
        x, y, width, height = box
        index = order[page]
        order[page] += 1
        spec = {"visualType": visual_type, "drillFilterOtherVisuals": visual_type != "textbox"}
        if roles:
            spec["query"] = {"queryState": {role: {"projections": bindings} for role, bindings in roles.items()}}
        if sort:
            spec["query"]["sortDefinition"] = {"sort": [{"field": sort, "direction": "Ascending"}]}
        if objects:
            spec["objects"] = objects
        if title:
            spec["visualContainerObjects"] = {
                "title": properties(show=literal(True), text=literal(title), fontColor=colour(INK), fontSize=literal(12)),
                "background": properties(show=literal(True), color=colour("#FFFFFF"), transparency=literal(0)),
                "border": properties(show=literal(True), color=colour("#D4DFE7"), radius=literal(8)),
            }
        write_json(definition / "pages" / page / "visuals" / name / "visual.json",
                   "item/report/definition/visualContainer/2.7.0", {
                       "name": name, "position": {"x": x, "y": y, "width": width, "height": height, "z": index,
                                                   "tabOrder": index}, "visual": spec,
                   })

    def text(page, key, box, lines):
        paragraphs = [{"textRuns": [{"value": value, "textStyle": {
            "fontFamily": "Segoe UI", "fontSize": f"{size}pt", "color": color,
        }}]} for value, size, color in lines]
        visual(page, key, "textbox", box, objects={"general": properties(paragraphs=paragraphs)})

    def header(page, title, subtitle):
        text(page, "header", (24, 16, 1392, 93), [
            ("CALPERS  /  PRIVATE MARKETS REVIEW", 11, TEAL), (title, 28, INK), (subtitle, 12, MUTED),
        ])

    def note(page, line):
        text(page, "note", (24, 742, 1392, 45), [(line, 11, MUTED)])

    def slicer(page, key, x, entity, name, width=300):
        visual(page, key, "slicer", (x, 117, width, 67),
               {"Values": [projection(entity, name, active=True)]},
               objects={"data": properties(mode=literal("Dropdown"))})

    def card(page, key, x, y, entity, measure, width=336):
        visual(page, key, "card", (x, y, width, 100), {"Values": [projection(entity, measure, "Measure")]},
               title=measure, objects={"categoryLabels": properties(show=literal(False))})

    header("portfolio", "Portfolio & vintage",
           "CalPERS fund snapshot  •  31 March 2026  •  Amounts in US dollars")
    slicer("portfolio", "programme", 24, "Programme", "Programme")
    slicer("portfolio", "vintage", 340, "Vintage", "Vintage")
    for i, measure in enumerate(("Fund Count", "Paid In", "Residual NAV", "IRR Flags")):
        card("portfolio", measure, 24 + 352 * i, 194, "Funds", measure)
    for i, metric in enumerate(("DPI", "TVPI")):
        visual("portfolio", metric, "lineChart", (24 + 704 * i, 310, 688, 255), {
            "Category": [projection("Vintage", "Vintage", active=True)],
            "Series": [projection("Programme", "Programme")],
            "Y": [projection("Funds", f"Median {metric}", "Measure")],
            "Tooltips": [projection("Funds", f"{metric} Observations", "Measure")],
        }, title=f"Median {metric} by vintage", sort=field("Vintage", "Vintage"),
               objects={"markers": properties(show=literal(True))})
    visual("portfolio", "quality", "tableEx", (24, 582, 1392, 145), {"Values": [
        projection("Programme", "Programme"), projection("Funds", "Multiple Check"),
        projection("Funds", "Fund Count", "Measure"), projection("Funds", "IRR Flags", "Measure"),
        projection("Funds", "IRR Available", "Measure"),
    ]}, title="Reported multiple reconciliation and usable IRR coverage")
    note("portfolio", "Cohorts include early-life funds with computable ratios. Hover for sample size. Vintage is CalPERS’ first cash-flow year.")

    header("manager", "Manager due diligence",
           "Advent Global Private Equity and Ares Senior Direct Lending  •  Eight case-study funds")
    slicer("manager", "manager", 24, "Manager", "Manager", 360)
    visual("manager", "decomposition", "columnChart", (24, 196, 1392, 258), {
        "Category": [projection("Case Funds", "Fund", active=True)],
        "Y": [projection("Case Funds", "Distributed Value", "Measure", label="DPI"),
              projection("Case Funds", "Unrealised Value", "Measure", label="RVPI")],
        "Tooltips": [projection("Case Funds", "TVPI"), projection("Case Funds", "Realised Share")],
    }, title="Distributed and unrealised value per dollar paid in", sort=field("Case Funds", "Fund"))
    visual("manager", "track record", "tableEx", (24, 470, 1392, 257), {"Values": [
        projection("Case Funds", name) for name in ("Fund", "Vintage", "DPI", "RVPI", "TVPI",
          "Realised Share", "Peer n", "Peer Median TVPI", "Quartile", "Review Status")
    ]}, title="Track record and eligible same-programme, same-vintage peers", sort=field("Case Funds", "Vintage"))
    note("manager", "Peer quartiles require eight eligible funds. Early-life funds stay visible for context and have no peer rank.")

    header("cashflow", "Distribution timing",
           "Illustrative Takahashi–Alexander-style model  •  Base case vs distributions one year later")
    for i, measure in enumerate(("Base XIRR", "Delayed XIRR", "XIRR Change")):
        card("cashflow", measure, 24 + 469 * i, 120, "Scenario", measure, 452)
    visual("cashflow", "cashflow", "lineChart", (24, 237, 1392, 330), {
        "Category": [projection("Cash Flow", "Quarter End", active=True)],
        "Series": [projection("Scenario", "Scenario")],
        "Y": [projection("Cash Flow", "Cumulative Net Flow", "Measure")],
    }, title="Cumulative net cash flow per 100 committed", sort=field("Cash Flow", "Quarter End"))
    visual("cashflow", "comparison", "tableEx", (24, 582, 1392, 147), {"Values": [
        projection("Scenario", name) for name in ("Scenario", "XIRR", "TVPI", "KS PME", "Direct Alpha",
                                                   "Funding Trough", "Terminal NAV")
    ]}, title="Scenario results  •  S&P 500 total-return benchmark", sort=field("Scenario", "Scenario"))
    note("cashflow", "Calls and nominal proceeds are identical. Delayed interim NAV is unavailable. This model uses illustrative cash flows.")


def make_preview(funds, cohorts, cashflows, results):
    def compact(fund):
        return [PROGRAMMES[fund["program"]], int(fund["vintage"]), int(fund["paid_in"]),
                int(fund["nav"]), number(fund["dpi"]), number(fund["tvpi"]),
                STATUS[fund["multiple_check"]], fund["irr_multiple_inconsistent"] == "True",
                fund["manager"], FUND_LABELS.get(fund["fund"]), number(fund["rvpi"]),
                number(fund["realised_share"]), number(fund["eligible_cohort_n"]),
                number(fund["cohort_median_tvpi"]), number(fund["sample_quartile"]),
                fund["early_life_flag"] == "True"]
    preview = {
        "funds": [compact(f) for f in funds],
        "cohorts": [[PROGRAMMES[c["program"]], int(c["vintage"]), int(c["rows"]), int(c["dpi_n"]),
                     number(c["median_dpi"]), number(c["median_tvpi"])] for c in cohorts],
        "flows": {key: [[row["date"], float(row["cumulative_net_cashflow"])] for row in rows]
                  for key, rows in cashflows.items()},
        "results": results,
    }
    template = (HERE / "preview_template.html").read_text(encoding="utf-8")
    payload = json.dumps(preview, separators=(",", ":"), ensure_ascii=True).replace("<", r"\u003c")
    (HERE / "CalPERS-preview.html").write_text(template.replace("/* SNAPSHOT_DATA */", payload), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-sql", action="store_true", help=f"Reconcile the PostgreSQL exports in {BUILD.name}")
    args = parser.parse_args()
    funds, cohorts, max_delta = check_funds()
    cashflows, results = check_cashflows()
    if args.check_sql:
        cohorts = compare_sql(funds, cohorts)
    make_model(funds, cashflows, results)
    make_report()
    make_preview(funds, cohorts, cashflows, results)
    print(f"Verified {len(funds)} source rows, {len(cohorts)} cohorts and {sum(map(len, cashflows.values()))} cash-flow rows.")
    print(f"Maximum absolute TVPI difference for 407 reported multiples: {max_delta:.6f}x.")


if __name__ == "__main__":
    main()
