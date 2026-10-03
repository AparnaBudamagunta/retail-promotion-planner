
import os
import time
import json
from litellm import completion

os.environ["GROQ_API_KEY"] = dbutils.secrets.get(
    scope="my_scope",
    key="groq_api_key"
)
os.environ["LLM_MODEL"] = "groq/openai/gpt-oss-20b"

SYSTEM_PROMPT = """
You are a senior retail promotion planning expert.

CRITICAL: Output only the final plan sections.
Never show internal thinking or deliberation.

THREE RULES:

1. GOAL CONSISTENCY
   The manager's goal comes ONLY from their words.
   Never infer the goal from the data.
   Data tells you what is available.
   The manager's words tell you what they want.
   If the goal is not clear from their words
   ask one question before building the plan.

2. DATA ACCURACY
   Every value in your plan must come directly
   from the data or pre-calculated simulation.
   This includes numbers, text fields, labels
   and categorisations provided in the data.
   Never recalculate, reword or reinterpret
   any value that already exists in the data.
   Use it exactly as it appears.

3. HONEST REASONING
   If a constraint cannot be satisfied explain why.
   Never pretend a problem does not exist.

PRODUCT SELECTION:
   If manager named a specific product
   build the plan around that product only.
   Respect the manager's choice.
   Only flag a concern if there is a genuine
   hard reason — zero stock, margin breach.

   If manager named only a category
   recommend the best 2-3 products from
   the simulation results.
   Use net gain and goal alignment to decide.
   Exclude products where simulation shows
   net gain is negative across all scenarios
   or stock is too low to sustain a promotion.
   State the reason for any exclusion clearly.

SEGMENT DIFFERENTIATION:
   Never apply the same discount to all segments.
   Use the discount range from the simulation
   (comp_discount to max_discount) to assign
   different offers per segment.
   Base the differentiation on each segment is
   price_sensitivity and discount_response
   from the segment data provided.
   Higher sensitivity deeper in the range.
   Lower sensitivity shallower or non-price offer.
   Lapsed segment reactivation offer.
   Premium segment non-price offer where possible.

OUTPUT SECTIONS:

SECTION 1 - RECOMMENDATION
SECTION 2 - PRODUCT REASONING
SECTION 3 - P&L SIMULATION
SECTION 4 - CONSTRAINT VALIDATION
SECTION 5 - CANNIBALIZATION RISK
SECTION 6 - SEGMENT PLAYBOOK
SECTION 7 - COMPETITOR CONTEXT
SECTION 8 - EXECUTION CHECKLIST
SECTION 9 - AI REASONING SUMMARY
SECTION 10 - BETTER ALTERNATIVE
"""


def calculate_promotions_simulation(
        inventory: list,
        competitor_prices: list,
        benchmarks: list,
        event_details: dict,
        marketing_budget: float,
        currency: str,
        min_margin_pct: float = 20.0) -> dict:
    """
    Calculates P&L simulation for every product.
    Returns full simulation + LLM summary + sections.
    """

    # Duration and multiplier from event data
    if event_details:
        demand_multiplier = event_details.get(
            "demand_multiplier", 1.0
        )
        promotion_days = event_details.get(
            "duration_days"
        )
    else:
        demand_multiplier = 1.0
        promotion_days    = None

    if not promotion_days:
        return {
            "simulation_possible": False,
            "reason": (
                "Promotion duration unknown. "
                "No event specified and manager "
                "did not state how long to run. "
                "Ask: how many days?"
            )
        }

    # Elasticity lookup
    elasticity_map = {}
    for b in benchmarks:
        key = f"{b['category']}_{b['geography']}"
        elasticity_map[key] = b.get(
            "price_elasticity", 2.0
        )

    # Cannibalization rate lookup
    cannib_map = {}
    for b in benchmarks:
        key = f"{b['category']}_{b['geography']}"
        cannib_map[key] = b.get(
            "cannibalization_rate", 0.18
        )

    # Competitor price lookup
    comp_map = {}
    for c in competitor_prices:
        sku = c["sku_id"]
        if sku not in comp_map:
            comp_map[sku] = []
        comp_map[sku].append(c["competitor_price"])

    # Simulate each product
    simulations = []

    for product in inventory:
        sku_id        = product["sku_id"]
        product_name  = product["product_name"]
        base_price    = product["base_price"]
        cogs          = product["cogs"]
        category      = product["category"]
        geography     = product["geography"]
        current_stock = product["current_stock"]
        avg_daily     = product["avg_daily_sales"]
        stock_status  = product["stock_status"]
        margin_pct    = product["margin_pct"]
        brand         = product["brand"]

        # Get elasticity
        key = f"{category}_{geography}"
        elasticity = elasticity_map.get(
            key, elasticity_map.get(
                f"{category}_global", 2.0
            )
        )

        # Get cannibalization rate
        cannib_rate = cannib_map.get(
            key, cannib_map.get(
                f"{category}_global", 0.18
            )
        )

        # Max discount from margin floor
        min_margin_dec = min_margin_pct / 100
        max_discount = 1 - cogs / (
            base_price * (1 - min_margin_dec)
        )
        max_discount = round(
            max(0, min(max_discount, 0.99)), 4
        )

        # Competitor discount
        comp_prices = comp_map.get(sku_id, [])
        if comp_prices:
            cheapest = min(comp_prices)
            if cheapest < base_price:
                comp_discount = round(
                    1 - (cheapest - 1) / base_price, 4
                )
                comp_discount = max(0.0, comp_discount)
                price_gap = round(
                    base_price - cheapest, 2
                )
                gap_direction = "WE ARE MORE EXPENSIVE"
            else:
                comp_discount = 0.0
                price_gap = round(
                    base_price - cheapest, 2
                )
                gap_direction = "WE ARE CHEAPER"
        else:
            comp_discount = 0.0
            price_gap     = 0.0
            gap_direction = "NO COMPETITOR DATA"

        # Max volume discount
        if elasticity > 1:
            max_vol_discount = round(
                (1 - 1 / elasticity) / 2, 4
            )
        else:
            max_vol_discount = round(
                max_discount * 0.3, 4
            )

        # Build discount levels
        discount_set = set()
        if 0 < comp_discount < max_discount:
            discount_set.add(comp_discount)
        if 0 < max_vol_discount < max_discount:
            discount_set.add(max_vol_discount)
        midpoint = round(
            (comp_discount + max_discount) / 2, 4
        )
        if 0 < midpoint < max_discount:
            discount_set.add(midpoint)
        if not discount_set:
            discount_set.add(
                round(max_discount * 0.5, 4)
            )

        discount_levels = sorted(discount_set)

        # Run scenarios
        scenarios_all = []
        for discount_pct in discount_levels:
            promo_price = base_price * (1 - discount_pct)
            margin_at_promo = (
                (promo_price - cogs) / promo_price * 100
            )
            if margin_at_promo < min_margin_pct:
                continue

            volume_uplift = discount_pct * elasticity
            daily_promo   = (
                avg_daily * demand_multiplier
                * (1 + volume_uplift)
            )

            if abs(discount_pct - comp_discount) < 0.001:
                source = "competitor_based"
            elif abs(discount_pct - max_vol_discount) < 0.001:
                source = "max_volume"
            else:
                source = "margin_midpoint"

            for scenario, factor in [
                ("pessimistic", 0.7),
                ("base",        1.0),
                ("optimistic",  1.3)
            ]:
                units = min(
                    current_stock,
                    round(
                        daily_promo * factor
                        * promotion_days
                    )
                )
                revenue      = round(units * promo_price, 2)
                cogs_total   = round(units * cogs, 2)
                gross_profit = round(revenue - cogs_total, 2)
                net_gain     = round(
                    gross_profit - marketing_budget, 2
                )

                scenarios_all.append({
                    "scenario":          scenario,
                    "discount_pct":      round(
                        discount_pct * 100, 1
                    ),
                    "discount_source":   source,
                    "promo_price":       round(promo_price, 2),
                    "margin_pct":        round(margin_at_promo, 1),
                    "volume_uplift_pct": round(
                        volume_uplift * 100, 1
                    ),
                    "daily_promo_units": round(daily_promo, 1),
                    "units":             units,
                    "revenue":           revenue,
                    "cogs_total":        cogs_total,
                    "gross_profit":      gross_profit,
                    "net_gain":          net_gain,
                    "stock_ceiling_hit": (
                        units >= current_stock
                    ),
                    "margin_constraint": (
                        "PASS"
                        if margin_at_promo >= min_margin_pct
                        else "FAIL"
                    )
                })

        # Find best discount
        best_net_gain  = None
        best_discount  = None
        best_scenario  = None

        for s in scenarios_all:
            if s["scenario"] == "base":
                if best_net_gain is None or \
                   s["net_gain"] > best_net_gain:
                    best_net_gain  = s["net_gain"]
                    best_discount  = s["discount_pct"]
                    best_scenario  = s

        simulations.append({
            "sku_id":              sku_id,
            "product_name":        product_name,
            "category":            category,
            "brand":               brand,
            "base_price":          base_price,
            "cogs":                cogs,
            "current_stock":       current_stock,
            "avg_daily_sales":     avg_daily,
            "stock_status":        stock_status,
            "base_margin_pct":     margin_pct,
            "elasticity":          elasticity,
            "cannib_rate":         cannib_rate,
            "demand_multiplier":   demand_multiplier,
            "promotion_days":      promotion_days,
            "currency":            currency,
            "price_gap":           price_gap,
            "gap_direction":       gap_direction,
            "cheapest_comp_price": min(comp_prices) if comp_prices else None,
            "discount_analysis": {
                "max_discount_pct":     round(max_discount * 100, 1),
                "comp_discount_pct":    round(comp_discount * 100, 1),
                "max_vol_discount_pct": round(max_vol_discount * 100, 1)
            },
            "recommended_discount_pct": best_discount,
            "recommended_net_gain":     best_net_gain,
            "recommended_scenario":     best_scenario,
            "scenarios":                scenarios_all
        })

    # Identify promoted products
    promoted = [
        p for p in simulations
        if p.get("recommended_net_gain") is not None
        and p["recommended_net_gain"] > 0
    ]

    # Calculate cannibalization
    promoted_skus = {p["sku_id"] for p in promoted}
    cannibalization = []
    # Get categories of promoted products
    promoted_categories = {
        p["category"] for p in simulations
        if p["sku_id"] in promoted_skus
    }

    for prod in simulations:
        if prod["sku_id"] in promoted_skus:
            continue
        # Only cannibalize within same category
        if prod["category"] not in promoted_categories:
            continue
        base_units = round(
            prod["avg_daily_sales"] * promotion_days
        )
        units_lost = round(
            base_units * prod["cannib_rate"], 1
        )
        margin_lost = round(
            units_lost * (prod["base_price"] - prod["cogs"]), 2
        )
        cannibalization.append({
            "sku_id":        prod["sku_id"],
            "product_name":  prod["product_name"],
            "brand":         prod["brand"],
            "base_units":    base_units,
            "cannib_rate":   prod["cannib_rate"],
            "units_lost":    units_lost,
            "margin_lost":   margin_lost,
            "currency":      currency
        })

    total_units_lost  = round(
        sum(c["units_lost"] for c in cannibalization), 1
    )
    total_margin_lost = round(
        sum(c["margin_lost"] for c in cannibalization), 2
    )

    return {
        "simulation_possible":   True,
        "simulations":           simulations,
        "promoted_products":     promoted,
        "cannibalization":       cannibalization,
        "cannibalization_summary": {
            "total_units_lost":  total_units_lost,
            "total_margin_lost": total_margin_lost,
            "currency":          currency
        },
        "marketing_budget":      marketing_budget,
        "currency":              currency,
        "demand_multiplier":     demand_multiplier,
        "promotion_days":        promotion_days,
        "min_margin_pct":        min_margin_pct,
        "total_evaluated":       len(simulations)
    }


def build_llm_summary(
        simulation: dict,
        context: dict,
        original_request: str) -> str:
    """
    Builds compact summary for LLM decision call.
    Scales to any data volume.
    LLM sees key facts only — not raw data.
    """
    currency = simulation["currency"]
    event    = context.get("event_details")

    lines = []
    lines.append(f"MANAGER REQUEST: {original_request}")
    lines.append(f"GOAL: {context.get('goal', 'unknown')}")
    lines.append("")

    if event:
        lines.append(
            f"EVENT: {event['name']} | "
            f"{event['start_date']} to {event['end_date']} | "
            f"{event['duration_days']} days | "
            f"demand multiplier {event['demand_multiplier']}x"
        )
    else:
        lines.append("EVENT: None specified")
    lines.append("")

    lines.append(
        f"BUDGET: {simulation['marketing_budget']} {currency}"
    )
    lines.append(
        f"CONSTRAINTS: min_margin={simulation['min_margin_pct']}%"
    )
    lines.append("")

    # All candidates — one row each
    lines.append(
        f"ALL CANDIDATES ({simulation['total_evaluated']} evaluated):"
    )
    lines.append(
        f"{'Product':<25} {'Status':<12} "
        f"{'Margin':>7} {'MarginOK':>9} "
        f"{'Rec Disc':>9} {'Net Gain':>10} "
        f"{'Comp Gap':>10}"
    )
    lines.append("-" * 85)

    for p in simulation["simulations"]:
        ng = p.get("recommended_net_gain")
        ng_str = f"{ng:>10.2f}" if ng is not None else "      N/A"
        margin_ok = (
            "PASS" if p["base_margin_pct"] >= simulation["min_margin_pct"]
            else "FAIL"
        )
        lines.append(
            f"{p['product_name']:<25} "
            f"{p['stock_status']:<12} "
            f"{p['base_margin_pct']:>6.1f}% "
            f"{margin_ok:>9} "
            f"{p['recommended_discount_pct'] or 0:>8.1f}% "
            f"{ng_str} "
            f"{p['gap_direction'][:10]:>10}"
        )
    lines.append("")

    # Brand relationships
    lines.append("BRAND RELATIONSHIPS:")
    brands = {}
    for p in simulation["simulations"]:
        b = p["brand"]
        if b not in brands:
            brands[b] = []
        brands[b].append(p["product_name"])
    for brand, products in brands.items():
        if len(products) > 1:
            lines.append(f"  {brand}: {', '.join(products)}")
    lines.append("")

    # Segment summary
    lines.append("CUSTOMER SEGMENTS:")
    for s in context.get("customer_segments", []):
        lines.append(
            f"  {s['segment_name']}: "
            f"sensitivity={s['price_sensitivity']} "
            f"response={s['discount_response']} "
            f"size={s['segment_size']}"
        )
    lines.append("")

    # Cannibalization summary
    cs = simulation.get("cannibalization_summary", {})
    lines.append(
        f"CANNIBALIZATION RISK: "
        f"total units at risk={cs.get('total_units_lost', 0)} | "
        f"margin at risk={cs.get('total_margin_lost', 0)} {currency}"
    )

    return "\n".join(lines)


def build_section_1(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:
    """Builds Section 1 — Recommendation."""
    currency = simulation["currency"]
    selected = decisions.get("selected_skus", [])

    # Get simulation data for selected SKUs
    selected_data = [
        p for p in simulation["simulations"]
        if p["sku_id"] in selected
    ]

    lines = []
    lines.append("## SECTION 1 - RECOMMENDATION")
    lines.append("")
    lines.append(f"**Goal:** {decisions.get('goal_statement', '')}")
    lines.append(
        f"**Event:** "
        f"{context['event_details']['name'] if context.get('event_details') else 'No event'}"
    )
    lines.append(
        f"**Promotion window:** "
        f"{context['event_details']['start_date'] if context.get('event_details') else 'TBD'}"
        f" to "
        f"{context['event_details']['end_date'] if context.get('event_details') else 'TBD'}"
    )
    budget = simulation['marketing_budget']
    if budget == 0:
        lines.append(
            "**Marketing budget:** Not specified "
            "_(net gain shown is gross profit only)_"
        )
    else:
        lines.append(
            f"**Marketing budget:** "
            f"{budget:,.0f} {currency}"
        )
    lines.append("")

    # Recommendation table
    lines.append("**Promoted Products:**")
    lines.append("")
    lines.append(
        f"| Product | SKU | Discount | "
        f"Promo Price | Margin | Stock | "
        f"Base Net Gain |"
    )
    lines.append(
        f"|---------|-----|----------|"
        f"------------|--------|-------|"
        f"--------------|"
    )

    total_net_gain = 0
    for p in selected_data:
        disc = p["recommended_discount_pct"] or 0
        sc   = p.get("recommended_scenario", {})
        ng   = p.get("recommended_net_gain", 0) or 0
        total_net_gain += ng
        lines.append(
            f"| {p['product_name']} "
            f"| {p['sku_id']} "
            f"| {disc}% "
            f"| {sc.get('promo_price', 0):,.2f} {currency} "
            f"| {sc.get('margin_pct', 0):.1f}% "
            f"| {p['current_stock']:,} units "
            f"| {ng:,.2f} {currency} |"
        )

    lines.append("")
    lines.append(
        f"**Total Expected Net Gain (Base):** "
        f"{total_net_gain:,.2f} {currency}"
    )
    lines.append("")

    # Segment discount table
    seg_discounts = decisions.get("segment_discounts", {})
    if seg_discounts and selected_data:
        lines.append("**Segment-Specific Discounts:**")
        lines.append("")
        header = "| Segment |"
        divider = "|---------|"
        for p in selected_data:
            header  += f" {p['product_name']} |"
            divider += "---------|"
        lines.append(header)
        lines.append(divider)

        segments = context.get("customer_segments", [])
        for seg in segments:
            sname = seg["segment_name"]
            row = f"| {sname} |"
            for p in selected_data:
                disc_range = p["discount_analysis"]
                comp_d = disc_range["comp_discount_pct"]
                max_d  = disc_range["max_discount_pct"]
                sens   = seg["price_sensitivity"]
                # Calculate segment discount from data
                # Higher sensitivity → deeper discount
                seg_disc = round(
                    comp_d + (max_d - comp_d) * sens, 1
                )
                mech = decisions.get(
                    "segment_mechanism", {}
                ).get(sname, "price_discount")
                row += f" {seg_disc}% ({mech}) |"
            lines.append(row)

    return "\n".join(lines)


def build_section_2(
        decisions: dict,
        simulation: dict) -> str:
    """Builds Section 2 — Product Reasoning."""
    currency = simulation["currency"]
    selected = decisions.get("selected_skus", [])

    lines = []
    lines.append("## SECTION 2 - PRODUCT REASONING")
    lines.append("")
    lines.append(
        f"**Total products evaluated:** "
        f"{simulation['total_evaluated']}"
    )
    lines.append(
        f"**Excluded:** "
        f"{decisions.get('excluded_reasoning', '')}"
    )
    lines.append("")
    lines.append("**Selected Products:**")
    lines.append("")
    lines.append(
        f"| Product | Stock | Status | "
        f"Margin | Rec Discount | Net Gain | Reasoning |"
    )
    lines.append(
        f"|---------|-------|--------|"
        f"--------|-------------|----------|-----------|"
    )

    for p in simulation["simulations"]:
        if p["sku_id"] not in selected:
            continue
        reasoning = decisions.get(
            "selection_reasoning", {}
        ).get(p["sku_id"], "")
        ng = p.get("recommended_net_gain", 0) or 0
        lines.append(
            f"| {p['product_name']} "
            f"| {p['current_stock']:,} "
            f"| {p['stock_status']} "
            f"| {p['recommended_scenario'].get('margin_pct', p['base_margin_pct']):.1f}% "
            f"| {p['recommended_discount_pct'] or 0:.1f}% "
            f"| {ng:,.2f} {currency} "
            f"| {reasoning} |"
        )

    lines.append("")
    lines.append(
        "*Full exclusion details available on request.*"
    )

    return "\n".join(lines)


def build_section_3(
        decisions: dict,
        simulation: dict) -> str:
    """Builds Section 3 — P&L Simulation."""
    currency = simulation["currency"]
    selected = decisions.get("selected_skus", [])

    lines = []
    lines.append("## SECTION 3 - P&L SIMULATION")
    lines.append(
        f"*All figures pre-calculated by PySpark. "
        f"Promotion: {simulation['promotion_days']} days | "
        f"Demand multiplier: {simulation['demand_multiplier']}x*"
    )
    lines.append("")

    for p in simulation["simulations"]:
        if p["sku_id"] not in selected:
            continue

        disc = p["recommended_discount_pct"] or 0
        lines.append(
            f"**{p['product_name']} "
            f"— {disc}% discount | "
            f"Source: {p['recommended_scenario'].get('discount_source', '') if p.get('recommended_scenario') else ''}**"
        )
        lines.append("")
        lines.append(
            f"| Scenario | Units | "
            f"Revenue ({currency}) | "
            f"Gross Profit ({currency}) | "
            f"Net Gain ({currency}) | "
            f"Stock Ceiling |"
        )
        lines.append(
            f"|----------|-------|"
            f"------------------|"
            f"----------------------|"
            f"------------------|"
            f"---------------|"
        )

        for s in p["scenarios"]:
            if s["discount_pct"] != disc:
                continue
            ceiling = "⚠️ HIT" if s["stock_ceiling_hit"] \
                else "No"
            lines.append(
                f"| {s['scenario']} "
                f"| {s['units']:,} "
                f"| {s['revenue']:,.2f} "
                f"| {s['gross_profit']:,.2f} "
                f"| {s['net_gain']:,.2f} "
                f"| {ceiling} |"
            )
        lines.append("")

    return "\n".join(lines)


def build_section_4(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:
    """Builds Section 4 — Constraint Validation."""
    currency  = simulation["currency"]
    selected  = decisions.get("selected_skus", [])
    budget    = simulation["marketing_budget"]
    min_marg  = simulation["min_margin_pct"]

    lines = []
    lines.append("## SECTION 4 - CONSTRAINT VALIDATION")
    lines.append("")
    lines.append(
        f"| Constraint | Requirement | "
        + " | ".join([
            p["product_name"]
            for p in simulation["simulations"]
            if p["sku_id"] in selected
        ])
        + " | Overall |"
    )
    lines.append(
        f"|------------|-------------|"
        + "---------|" * (len(selected) + 1)
    )

    selected_data = [
        p for p in simulation["simulations"]
        if p["sku_id"] in selected
    ]

    # Margin check
    row = f"| Min margin | ≥{min_marg}% |"
    all_pass = True
    for p in selected_data:
        sc = p.get("recommended_scenario", {})
        margin = sc.get("margin_pct", 0) if sc else 0
        status = "PASS" if margin >= min_marg else "FAIL"
        if status == "FAIL":
            all_pass = False
        row += f" {status} ({margin:.1f}%) |"
    row += f" {'PASS' if all_pass else 'FAIL'} |"
    lines.append(row)

    # Discount check
    row = f"| Max discount | ≤45% |"
    all_pass = True
    for p in selected_data:
        disc = p["recommended_discount_pct"] or 0
        status = "PASS" if disc <= 45 else "FAIL"
        if status == "FAIL":
            all_pass = False
        row += f" {status} ({disc:.1f}%) |"
    row += f" {'PASS' if all_pass else 'FAIL'} |"
    lines.append(row)

    # Budget check
    if budget == 0:
        row = f"| Marketing budget | Not specified |"
        for p in selected_data:
            row += f" Not specified |"
        row += f" PASS |"
    else:
        row = f"| Marketing budget | ≤{budget:,.0f} {currency} |"
        budget_per = round(budget / len(selected_data), 0) \
            if selected_data else 0
        for p in selected_data:
            row += f" {budget_per:,.0f} {currency} |"
        row += f" PASS |"
    lines.append(row)

    # Stock check
    row = f"| Stock availability | Units sold ≤ stock |"
    all_pass = True
    for p in selected_data:
        sc = p.get("recommended_scenario", {})
        opt_units = 0
        for s in p.get("scenarios", []):
            if s["scenario"] == "optimistic" and \
               s["discount_pct"] == p["recommended_discount_pct"]:
                opt_units = s["units"]
                break
        status = "PASS" \
            if opt_units <= p["current_stock"] \
            else "FAIL"
        if status == "FAIL":
            all_pass = False
        row += (
            f" {status} "
            f"({opt_units:,}≤{p['current_stock']:,}) |"
        )
    row += f" {'PASS' if all_pass else 'FAIL'} |"
    lines.append(row)

    return "\n".join(lines)


def build_section_5(simulation: dict) -> str:
    """Builds Section 5 — Cannibalization Risk."""
    currency = simulation["currency"]
    cs       = simulation.get("cannibalization_summary", {})
    cannibal = simulation.get("cannibalization", [])

    lines = []
    lines.append("## SECTION 5 - CANNIBALIZATION RISK")
    lines.append("")
    lines.append(
        f"**Total units at risk:** "
        f"{cs.get('total_units_lost', 0):,.1f}"
    )
    lines.append(
        f"**Total margin at risk:** "
        f"{cs.get('total_margin_lost', 0):,.2f} {currency}"
    )
    lines.append("")

    if cannibal:
        top3 = sorted(
            cannibal,
            key=lambda x: x["margin_lost"],
            reverse=True
        )[:3]

        lines.append("**Top affected own products:**")
        lines.append("")
        lines.append(
            f"| Product | Brand | "
            f"Base Units | Rate | "
            f"Units Lost | Margin Lost ({currency}) |"
        )
        lines.append(
            f"|---------|-------|"
            f"-----------|------|"
            f"-----------|----------------------|"
        )
        for c in top3:
            lines.append(
                f"| {c['product_name']} "
                f"| {c['brand']} "
                f"| {c['base_units']:,} "
                f"| {c['cannib_rate']:.2f} "
                f"| {c['units_lost']:,.1f} "
                f"| {c['margin_lost']:,.2f} |"
            )

    lines.append("")
    lines.append(
        "*Net category impact: Cannibalization loss is "
        f"{cs.get('total_margin_lost', 0):,.2f} {currency}. "
        "Offset by promoted products net gain.*"
    )

    return "\n".join(lines)


def build_section_6(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:
    """Builds Section 6 — Segment Playbook."""
    currency     = simulation["currency"]
    selected     = decisions.get("selected_skus", [])
    selected_data = [
        p for p in simulation["simulations"]
        if p["sku_id"] in selected
    ]
    segments     = context.get("customer_segments", [])

    lines = []
    lines.append("## SECTION 6 - SEGMENT PLAYBOOK")
    lines.append("")
    lines.append(
        f"| Segment | Size | "
        + " | ".join([
            f"{p['product_name']} Discount"
            for p in selected_data
        ])
        + " | Mechanism | Channel | KPI |"
    )
    lines.append(
        f"|---------|------|"
        + "---------|" * len(selected_data)
        + "-----------|---------|-----|"
    )

    for seg in segments:
        sname = seg["segment_name"]
        sens  = seg["price_sensitivity"]
        mech  = decisions.get(
            "segment_mechanism", {}
        ).get(sname, "price_discount")

        # Channel from segment data
        if sens < 0.3:
            channel = "Email + Loyalty App"
        elif sens < 0.6:
            channel = "SMS + In-store"
        else:
            channel = "SMS + Digital Ads"

        kpi = "Units sold + Margin"
        if sname == "lapsed":
            kpi = "Reactivation rate"
        elif sname == "loyalty_member":
            kpi = "Retention rate"

        row = f"| {sname} | {seg['segment_size']:,} |"

        for p in selected_data:
            disc_range = p["discount_analysis"]
            comp_d = disc_range["comp_discount_pct"]
            max_d  = disc_range["max_discount_pct"]
            # Segment discount from sensitivity score
            seg_disc = round(
                comp_d + (max_d - comp_d) * sens, 1
            )
            if mech == "loyalty_points":
                row += f" Loyalty points |"
            else:
                row += f" {seg_disc}% |"

        row += f" {mech} | {channel} | {kpi} |"
        lines.append(row)

    return "\n".join(lines)


def build_section_7(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:
    """Builds Section 7 — Competitor Context."""
    selected     = decisions.get("selected_skus", [])
    comp_prices  = context.get("competitor_prices", [])

    lines = []
    lines.append("## SECTION 7 - COMPETITOR CONTEXT")
    lines.append("")
    lines.append(
        f"| Product | Competitor | "
        f"Our Price | Comp Price | Gap | Position |"
    )
    lines.append(
        f"|---------|------------|"
        f"-----------|------------|-----|----------|"
    )

    for c in comp_prices:
        # Only show promoted products
        matching = [
            p for p in simulation["simulations"]
            if p["sku_id"] == c["sku_id"]
            and p["sku_id"] in selected
        ]
        if not matching:
            continue
        prod = matching[0]
        gap  = round(
            c["our_price"] - c["competitor_price"], 2
        )
        lines.append(
            f"| {c['product_name']} "
            f"| {c['competitor_name']} "
            f"| {c['our_price']} "
            f"| {c['competitor_price']} "
            f"| {gap:+.2f} "
            f"| {c['position']} |"
        )

    return "\n".join(lines)


def build_section_8(
        decisions: dict,
        context: dict) -> str:
    """Builds Section 8 — Execution Checklist."""
    event = context.get("event_details")

    lines = []
    lines.append("## SECTION 8 - EXECUTION CHECKLIST")
    lines.append("")
    lines.append(
        f"| Phase | Action | Owner | Date |"
    )
    lines.append(
        f"|-------|--------|-------|------|"
    )

    if event:
        start = event["start_date"]
        end   = event["end_date"]
        days_until = event.get("days_until", 30)

        # Pre-launch actions
        urgency = "URGENT — " if days_until < 14 else ""
        lines.append(
            f"| Pre-Launch | Finalise discount codes "
            f"and POS pricing | Pricing Team | "
            f"{urgency}{max(0, days_until - 14)} days before event |"
        )
        lines.append(
            f"| Pre-Launch | Design promotional creatives "
            f"for each segment | Marketing | "
            f"{urgency}{max(0, days_until - 10)} days before event |"
        )
        lines.append(
            f"| Pre-Launch | Train store staff on "
            f"segment-specific offers | Retail Ops | "
            f"{days_until - 7} days before event |"
        )
        lines.append(
            f"| Pre-Launch | Schedule email SMS and "
            f"app notifications | Digital | "
            f"{days_until - 3} days before event |"
        )
        lines.append(
            f"| Launch | Activate all discounts "
            f"across channels | All Teams | {start} |"
        )
        lines.append(
            f"| During | Daily sales and stock "
            f"monitoring | Analytics | "
            f"{start} to {end} |"
        )
        lines.append(
            f"| During | Adjust messaging if "
            f"performance below base scenario | "
            f"Marketing | Mid-campaign |"
        )
        lines.append(
            f"| Post | Deactivate all discounts "
            f"| Pricing Team | {end} |"
        )
        lines.append(
            f"| Post | Calculate actual P&L vs "
            f"simulation | Finance | 3 days after end |"
        )
        lines.append(
            f"| Post | Document learnings for "
            f"next promotion | Analytics | "
            f"1 week after end |"
        )

    return "\n".join(lines)


def build_section_9(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:
    """Builds Section 9 — AI Reasoning Summary."""
    currency     = simulation["currency"]
    selected     = decisions.get("selected_skus", [])
    selected_data = [
        p for p in simulation["simulations"]
        if p["sku_id"] in selected
    ]
    cs = simulation.get("cannibalization_summary", {})

    lines = []
    lines.append("## SECTION 9 - AI REASONING SUMMARY")
    lines.append("")
    lines.append(
        f"**Goal identified:** "
        f"{decisions.get('goal_statement', '')}"
    )
    lines.append("")
    lines.append(
        f"**Products selected:** "
        + ", ".join([p["product_name"] for p in selected_data])
    )
    for p in selected_data:
        reasoning = decisions.get(
            "selection_reasoning", {}
        ).get(p["sku_id"], "")
        lines.append(f"  - {p['product_name']}: {reasoning}")
    lines.append("")
    lines.append(
        f"**Excluded products:** "
        f"{decisions.get('excluded_reasoning', '')}"
    )
    lines.append("")
    lines.append(
        f"**Discount logic:** "
        f"Competitor-based floor — beats cheapest competitor. "
        f"Segment depth scales with price sensitivity score."
    )
    lines.append("")
    lines.append(
        f"**Cannibalization:** "
        f"{cs.get('total_units_lost', 0):,.1f} units and "
        f"{cs.get('total_margin_lost', 0):,.2f} {currency} "
        f"margin at risk from own products."
    )
    lines.append("")
    budget = simulation['marketing_budget']
    if budget == 0:
        lines.append(
            "**Budget:** Not specified."
        )
    else:
        lines.append(
            f"**Budget:** "
            f"{budget:,.0f} {currency} fully allocated."
        )
    lines.append("")
    lines.append(
        f"**Confidence:** "
        f"Based on benchmark elasticity data. "
        f"Accuracy improves with historical promotion data."
    )

    return "\n".join(lines)


def build_section_10(decisions: dict) -> str:
    """Builds Section 10 — Better Alternative."""
    lines = []
    lines.append("## SECTION 10 - BETTER ALTERNATIVE")
    lines.append("")
    alt = decisions.get("better_alternative")
    if alt and alt.lower() != "null" and alt.lower() != "none":
        lines.append(alt)
    else:
        lines.append(
            "No better alternative identified. "
            "Current selection maximises net gain "
            "within constraints."
        )
    return "\n".join(lines)


def assemble_plan(
        decisions: dict,
        simulation: dict,
        context: dict) -> str:

    # Recalculate cannibalization using
    # only LLM selected products
    cannibal_data = recalculate_cannibalization(
        decisions, simulation
    )
    simulation["cannibalization"] = \
        cannibal_data["cannibalization"]
    simulation["cannibalization_summary"] = \
        cannibal_data["cannibalization_summary"]

    sections = [
        build_section_1(decisions, simulation, context),
        build_section_2(decisions, simulation),
        build_section_3(decisions, simulation),
        build_section_4(decisions, simulation, context),
        build_section_5(simulation),
        build_section_6(decisions, simulation, context),
        build_section_7(decisions, simulation, context),
        build_section_8(decisions, context),
        build_section_9(decisions, simulation, context),
        build_section_10(decisions),
    ]

    return "\n\n---\n\n".join(sections)


def recalculate_cannibalization(
        decisions: dict,
        simulation: dict) -> dict:
    """
    Recalculates cannibalization using
    only LLM selected products.
    Not all promoted candidates.
    """
    selected_skus = set(
        decisions.get("selected_skus", [])
    )

    # Get categories of selected products only
    selected_categories = {
        p["category"]
        for p in simulation["simulations"]
        if p["sku_id"] in selected_skus
    }

    currency = simulation["currency"]
    promotion_days = simulation["promotion_days"]
    cannibalization = []

    for prod in simulation["simulations"]:
        if prod["sku_id"] in selected_skus:
            continue
        if prod["category"] not in selected_categories:
            continue

        base_units = round(
            prod["avg_daily_sales"] * promotion_days
        )
        units_lost = round(
            base_units * prod["cannib_rate"], 1
        )
        margin_lost = round(
            units_lost * (prod["base_price"] - prod["cogs"]), 2
        )
        cannibalization.append({
            "sku_id":       prod["sku_id"],
            "product_name": prod["product_name"],
            "brand":        prod["brand"],
            "base_units":   base_units,
            "cannib_rate":  prod["cannib_rate"],
            "units_lost":   units_lost,
            "margin_lost":  margin_lost,
            "currency":     currency
        })

    total_units_lost = round(
        sum(c["units_lost"] for c in cannibalization), 1
    )
    total_margin_lost = round(
        sum(c["margin_lost"] for c in cannibalization), 2
    )

    return {
        "cannibalization": cannibalization,
        "cannibalization_summary": {
            "total_units_lost":  total_units_lost,
            "total_margin_lost": total_margin_lost,
            "currency":          currency
        }
    }


def get_promoted_products(simulation: dict) -> list:
    """Returns products with positive net gain."""
    return [
        p for p in simulation.get("simulations", [])
        if p.get("recommended_net_gain") is not None
        and p["recommended_net_gain"] > 0
    ]


def parse_scope(user_request: str) -> dict:
    """
    Extracts 6 fields for the system.
    4 for PySpark queries.
    1 for goal.
    1 for marketing budget.
    """
    print("Parsing scope from request...")

    prompt = f"""
Extract these 6 fields from the request.
Return ONLY valid JSON. No explanation. No markdown.

{{
  "category": "product category mentioned or all",
  "geography": "country or region mentioned or all",
  "event": "event or festival mentioned or null",
  "currency": "appropriate currency for the geography",
  "goal": "what the manager wants to achieve.
           Read their exact words and summarise.
           Examples:
             seasonal_capitalisation — festival or season mentioned
             inventory_clearance — clearing stock mentioned
             brand_promotion — brand partner mentioned
             competitive_response — competitor mentioned
             traffic_driver — footfall mentioned
             revenue_growth — grow sales mentioned
             unknown — genuinely unclear",
  "marketing_budget": "number if explicitly stated or null if not mentioned"
}}

Request: {user_request}
"""

    response = completion(
        model="groq/qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.0
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json","").replace("```","").strip()

    try:
        scope = json.loads(raw)
        print(f"  ✅ Scope parsed:")
        print(f"     Category:  {scope.get('category')}")
        print(f"     Geography: {scope.get('geography')}")
        print(f"     Event:     {scope.get('event')}")
        print(f"     Currency:  {scope.get('currency')}")
        print(f"     Goal:      {scope.get('goal')}")
        print(f"     Budget:    {scope.get('marketing_budget')}")
        return scope
    except json.JSONDecodeError:
        print("  ⚠️  Parse error — using safe defaults")
        return {
            "category":         "all",
            "geography":        "all",
            "event":            None,
            "currency":         "INR",
            "goal":             "unknown",
            "marketing_budget": None
        }


def build_promotion_context(
        category: str = "all",
        geography: str = "all",
        event: str = None,
        goal: str = None,
        specific_product: str = None,
        incoming_stock: int = None,
        incoming_date: str = None,
        marketing_budget: float = 10000,
        currency: str = "INR") -> dict:
    """
    Fetches ALL data the LLM needs
    to reason about a promotion plan.
    PySpark does all the heavy lifting.
    LLM receives clean structured context.
    """

    print("Building promotion context...")
    context = {}

    # ── 1. INVENTORY ──────────────────────────────
    print("  → Fetching inventory...")
    inv_query = """
        SELECT
            p.sku_id,
            p.product_name,
            p.category,
            p.geography,
            p.currency,
            p.base_price,
            p.cogs,
            p.brand,
            i.current_stock,
            i.avg_daily_sales,
            i.days_cover,
            i.stock_status,
            ROUND((p.base_price - p.cogs) /
                   p.base_price * 100, 1)
                   AS margin_pct
        FROM products p
        JOIN inventory_status i
          ON p.sku_id = i.sku_id
        WHERE 1=1
    """
    if category != "all":
        inv_query += f" AND LOWER(p.category) = LOWER('{category}')"
    if geography != "all":
        inv_query += f" AND p.geography = '{geography}'"

    if specific_product:
        inv_query += f"""
            AND (LOWER(p.product_name)
                 LIKE '%{specific_product.lower()}%'
                 OR p.sku_id = '{specific_product}')
        """

    inv_query += " ORDER BY i.days_cover DESC"
    inv_df = spark.sql(inv_query)
    context["inventory"] = inv_df.toPandas().to_dict(
        orient="records"
    )
    print(f"     {len(context['inventory'])} products found")

    # ── 2. COMPETITOR PRICES ──────────────────────
    print("  → Fetching competitor prices...")
    comp_query = """
        SELECT
            cp.sku_id,
            p.product_name,
            p.base_price AS our_price,
            p.currency,
            cp.competitor_name,
            cp.competitor_price,
            ROUND(p.base_price -
                  cp.competitor_price, 2)
                  AS price_gap,
            CASE
                WHEN p.base_price > cp.competitor_price
                THEN 'WE ARE MORE EXPENSIVE'
                WHEN p.base_price < cp.competitor_price
                THEN 'WE ARE CHEAPER'
                ELSE 'SAME PRICE'
            END AS position
        FROM competitor_prices cp
        JOIN products p
          ON cp.sku_id = p.sku_id
        WHERE 1=1
    """
    if category != "all":
        comp_query += f" AND LOWER(p.category) = LOWER('{category}')"
    if geography != "all":
        comp_query += f" AND cp.geography = '{geography}'"

    comp_df = spark.sql(comp_query)
    context["competitor_prices"] = comp_df.toPandas().to_dict(
        orient="records"
    )
    print(f"     {len(context['competitor_prices'])} competitor records")

    # ── 3. CUSTOMER SEGMENTS ──────────────────────
    print("  → Fetching customer segments...")
    seg_query = """
        SELECT
            segment_name,
            geography,
            segment_size,
            price_sensitivity,
            avg_basket_value,
            discount_response,
            loyalty_score,
            description
        FROM customer_segments
        WHERE 1=1
    """
    if geography != "all":
        seg_query += f" AND geography = '{geography}'"

    seg_df = spark.sql(seg_query)
    context["customer_segments"] = seg_df.toPandas().to_dict(
        orient="records"
    )
    print(f"     {len(context['customer_segments'])} segments found")

    # ── 4. UPCOMING HOLIDAYS ──────────────────────
    print("  → Fetching holidays...")
    hol_query = """
        SELECT
            event_name,
            geography,
            start_date,
            end_date,
            category_relevance,
            demand_multiplier,
            description,
            DATEDIFF(start_date,
                     current_date()) AS days_until,
            DATEDIFF(end_date, start_date) + 1
                AS event_duration_days
        FROM holiday_calendar
        WHERE start_date >= current_date()
        AND   start_date <= date_add(
                current_date(), 120)
    """
    if geography != "all":
        hol_query += f" AND geography = '{geography}'"
    if event:
        hol_query += f"""
            AND LOWER(event_name)
                LIKE '%{event.lower()}%'
        """
    hol_query += " ORDER BY start_date"

    hol_df = spark.sql(hol_query)
    context["holidays"] = hol_df.toPandas().to_dict(
        orient="records"
    )
    print(f"     {len(context['holidays'])} upcoming events")

    if context["holidays"]:
        primary = context["holidays"][0]
        context["event_details"] = {
            "name":              primary["event_name"],
            "start_date":        str(primary["start_date"]),
            "end_date":          str(primary["end_date"]),
            "duration_days":     primary["event_duration_days"],
            "days_until":        primary["days_until"],
            "demand_multiplier": primary["demand_multiplier"],
            "description":       primary["description"]
        }
        print(f"     Event: {primary['event_name']}")
        print(f"     Dates: {primary['start_date']} to {primary['end_date']}")
        print(f"     Days until: {primary['days_until']}")
    else:
        context["event_details"] = None

    # ── 5. BENCHMARKS ─────────────────────────────
    print("  → Fetching benchmarks...")
    bench_query = """
        SELECT *
        FROM benchmark_elasticity
        WHERE 1=1
    """
    if category != "all":
        bench_query += f"""
            AND category IN ('{category}', 'all')
        """
    if geography != "all":
        bench_query += f"""
            AND geography IN ('{geography}', 'global')
        """

    bench_df = spark.sql(bench_query)
    context["benchmarks"] = bench_df.toPandas().to_dict(
        orient="records"
    )
    print(f"     {len(context['benchmarks'])} benchmark records")

    # ── 6. PRODUCT RELATIONSHIPS ──────────────────
    print("  → Fetching product relationships...")
    if category != "all" and geography != "all":
        rel_query = f"""
            SELECT
                p.sku_id,
                p.product_name,
                p.category,
                p.brand,
                p.base_price,
                p.cogs,
                i.current_stock,
                i.stock_status,
                i.days_cover,
                ROUND((p.base_price - p.cogs) /
                       p.base_price * 100, 1)
                       AS margin_pct
            FROM products p
            JOIN inventory_status i
              ON p.sku_id = i.sku_id
            WHERE p.category = '{category}'
            AND   p.geography = '{geography}'
            ORDER BY p.brand, i.days_cover DESC
        """
        rel_df = spark.sql(rel_query)
        context["product_relationships"] = \
            rel_df.toPandas().to_dict(orient="records")
    else:
        context["product_relationships"] = []
    print(f"     {len(context['product_relationships'])} related products")

    # ── 7. CONSTRAINTS AND METADATA ───────────────
    context["constraints"] = {
        "minimum_margin_pct":        20,
        "marketing_budget":          marketing_budget,
        "currency":                  currency,
        "inventory_clearance_days":  30,
        "max_discount_pct":          45,
    }

    context["request_metadata"] = {
        "category":        category,
        "geography":       geography,
        "event":           event,
        "goal":            goal,
        "specific_product":specific_product,
        "incoming_stock":  incoming_stock,
        "incoming_date":   incoming_date,
        "marketing_budget":marketing_budget,
        "currency":        currency,
    }

    print("\n✅ Context built successfully")
    print(f"   Total data points: {sum([len(v) if isinstance(v, list) else 1 for v in context.values()])}")
    return context


def get_llm_decisions(
        simulation: dict,
        context: dict,
        original_request: str) -> dict:
    """
    Single LLM call — returns JSON decisions only.
    No numbers. No tables. Just judgements.
    """
    print("\nGetting LLM decisions...")

    summary = build_llm_summary(
        simulation, context, original_request
    )

    # Build SKU reference for LLM
    sku_reference = "\n".join([
        f"  {p['sku_id']}: {p['product_name']}"
        for p in simulation["simulations"]
    ])

    prompt = f"""
    You are a retail promotion planning expert.
    Read the situation below and return decisions as JSON.

    SKU REFERENCE (use these exact IDs in selected_skus):
    {sku_reference}

    {summary}

    Return ONLY this JSON — no explanation, no markdown:
    {{
    "selected_skus": ["SKU_BEV_001", "SKU_BEV_003"],
    "selection_reasoning": {{
        "SKU_BEV_001": "one sentence why selected",
        "SKU_BEV_003": "one sentence why selected"
    }},
    "excluded_reasoning": "one sentence why others excluded",
    "segment_mechanism": {{
        "premium": "loyalty_points",
        "mid_income": "price_discount",
        "price_sensitive": "price_discount",
        "loyalty_member": "loyalty_points",
        "lapsed": "price_discount"
    }},
    "goal_statement": "one sentence describing the goal",
    "marketing_budget": "number if explicitly stated in request or null if not mentioned",
    "better_alternative": null,
    "clarification_needed": false,
    "clarification_question": null,
    "marketing_budget": "extract the number only if manager explicitly states a budget amount. null if not mentioned.",
    "better_alternative": "if manager named a specific 
    product — suggest the top 1-2 products from same 
    category that could complement or outperform it.
    Show product name and net gain from simulation.
    If no better option exists write null."
    }}

    IMPORTANT EDGE CASES:
    If the requested brand or product is not
    in the catalog or no products have positive
    net gain:
    Set selected_skus to []
    Set clarification_needed to true
    Set clarification_question to a clear message:
        - State what went wrong
        - Ask what the manager wants to do next
        - Offer 2-3 specific options
    Do not generate an empty plan.
    """

    response = completion(
        model="groq/qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.0
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json","").replace("```","").strip()

    try:
        decisions = json.loads(raw)
        print(f"  ✅ Decisions received")
        print(f"     Selected: {decisions.get('selected_skus')}")
        print(f"     Goal: {decisions.get('goal_statement')}")
        return decisions
    except json.JSONDecodeError:
        print(f"  ⚠️  Parse error — raw: {raw[:200]}")
        # Fallback — use promoted products from simulation
        promoted = simulation.get("promoted_products", [])
        return {
            "selected_skus": [p["sku_id"] for p in promoted],
            "selection_reasoning": {
                p["sku_id"]: "highest net gain"
                for p in promoted
            },
            "excluded_reasoning": "negative net gain",
            "segment_mechanism": {
                "premium":        "loyalty_points",
                "mid_income":     "price_discount",
                "price_sensitive":"price_discount",
                "loyalty_member": "loyalty_points",
                "lapsed":         "price_discount"
            },
            "goal_statement": context.get("goal", ""),
            "better_alternative": None,
            "clarification_needed": False,
            "clarification_question": None
        }


def run_promotion_planner(user_request: str) -> str:
    """
    Main entry point.
    Stage 1: PySpark fetches data
    Stage 2: LLM makes decisions
    Stage 3: Code assembles plan
    """
    print(f"\n{'='*60}")
    print("AI PROMOTION PLANNER")
    print(f"{'='*60}")
    print(f"Request: {user_request}")
    print(f"{'='*60}\n")

    # CALL 1: Parse scope
    scope = parse_scope(user_request)

    if scope.get("goal") == "unknown":
        return """
Got it. One question before I build your plan:

What are you trying to achieve with this promotion?
Describe it in your own words.
"""

    time.sleep(2)

    # STAGE 1: PySpark fetches data
    context = build_promotion_context(
        category=scope.get("category", "all"),
        geography=scope.get("geography", "all"),
        event=scope.get("event"),
        currency=scope.get("currency", "INR")
    )
    context["goal"] = scope.get("goal")
    context["constraints"]["marketing_budget"] = \
        scope.get("marketing_budget") or 0    

    # STAGE 1b: PySpark calculates simulation
    print("\nRunning simulation...")
    simulation = calculate_promotions_simulation(
        inventory=context["inventory"],
        competitor_prices=context["competitor_prices"],
        benchmarks=context["benchmarks"],
        event_details=context.get("event_details"),
        marketing_budget=context["constraints"][
            "marketing_budget"
        ],
        currency=scope.get("currency", "INR"),
        min_margin_pct=context["constraints"][
            "minimum_margin_pct"
        ]
    )

    if not simulation.get("simulation_possible"):
        return f"Cannot run simulation: {simulation.get('reason')}"

    print(f"  ✅ {len(simulation['simulations'])} products simulated")
    print(f"  ✅ {len(simulation['promoted_products'])} promotion candidates")

    time.sleep(2)

    # STAGE 2: LLM makes decisions
    decisions = get_llm_decisions(
        simulation, context, user_request
    )

    # Handle clarification needed
    if decisions.get("clarification_needed"):
        return decisions.get(
            "clarification_question",
            "I need more information to proceed."
        )

    # STAGE 3: Code assembles complete plan
    print("\nAssembling plan...")
    plan = assemble_plan(decisions, simulation, context)

    print(f"\n{'='*60}")
    print("PLAN COMPLETE")
    print(f"{'='*60}\n")

    return plan


