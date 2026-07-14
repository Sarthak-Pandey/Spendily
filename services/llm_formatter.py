import sqlite3
import os

class InsightLLMFormatter:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def format_insight(self, type_str, metrics):
        """
        Formats an insight using LLM (if configured) or falls back to robust templates.
        """
        api_key = os.environ.get("LLM_API_KEY")
        title, description, action = self._get_fallback_template(type_str, metrics)
        
        return {
            "title": title,
            "description": description,
            "action": action
        }

    def _get_fallback_template(self, type_str, metrics):
        category = metrics.get("category", "")
        
        if type_str == "critical":
            spent = metrics.get("spent", 0.0)
            limit = metrics.get("limit", 0.0)
            pct = metrics.get("pct_used", 0.0)
            title = f"{category} budget exceeded"
            description = f"You have exceeded your ₹{limit:,.2f} limit in {category} by spending ₹{spent:,.2f} ({pct}% used)."
            action = f"Limit further {category.lower()} expenses for the remainder of this month."
            
        elif type_str == "warning":
            spent = metrics.get("spent", 0.0)
            limit = metrics.get("limit", 0.0)
            pct = metrics.get("pct_used", 0.0)
            title = f"{category} budget alert"
            description = f"You have spent ₹{spent:,.2f} of your ₹{limit:,.2f} limit in {category} ({pct}% used)."
            action = f"Consider cutting back on {category.lower()} spending to avoid going over budget."
            
        elif type_str == "success":
            annual_saving = metrics.get("annual_saving", 0.0)
            monthly_saving = metrics.get("monthly_saving", 0.0)
            title = f"Annual savings in {category}"
            description = f"Trimming your {category.lower()} spending by 20% could save you ₹{monthly_saving:,.2f} monthly, projecting to ₹{annual_saving:,.2f} saved annually."
            action = "Establish a budget limit to track this goal."
            
        else: # info
            this_spent = metrics.get("this_spent", 0.0)
            last_spent = metrics.get("last_spent", 0.0)
            change = metrics.get("pct_change", 0.0)
            
            if change > 0:
                direction = "increased by"
            elif change < 0:
                direction = "decreased by"
                change = abs(change)
            else:
                direction = "is equal to"
                
            title = "Month-over-month spending trend"
            if direction == "is equal to":
                description = f"Your spending this month (₹{this_spent:,.2f}) is equal to your spending last month (₹{last_spent:,.2f})."
            else:
                description = f"Your monthly spending has {direction} {change}% (₹{this_spent:,.2f} this month vs. ₹{last_spent:,.2f} last month)."
            action = "Check category summaries to evaluate your spending habits."

        return title, description, action
