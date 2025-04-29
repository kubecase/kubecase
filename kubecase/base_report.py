import os
from datetime import datetime
import typer
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import kubecase.utils as utils

class BaseReport(FPDF):
    """
    Base PDF class for KubeCase reports.
    Provides common setup: fonts, headers, footers, logos.
    """

    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.set_auto_page_break(auto=True, margin=15)
        self.add_fonts()
        self.mascot_path = utils.get_asset_path("mascot.png")
        self.report_title = "KubeCase Report"

    def add_fonts(self):
        """
        Add standard fonts used across all reports.
        """
        self.add_font('DejaVu', '', utils.get_font_path('DejaVuSansCondensed.ttf'), uni=True)
        self.add_font('DejaVu', 'B', utils.get_font_path('DejaVuSansCondensed-Bold.ttf'), uni=True)
    
    def header(self):
        """
        Common header for all pages.
        """
        if self.page_no() == 1:
            self.ln(15)
            self.set_font("Dejavu", 'B', 35)
            self.cell(0, 15, self.report_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(30)
        else:
            self.set_font("Dejavu", 'B', 18)
            self.cell(0, 10, self.report_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(5)

    def footer(self):
        """
        Common footer for all pages.
        """
        if self.page_no() != 1:
          self.set_y(-15)
          self.set_font('DejaVu', '', 8)
          self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_metadata_table_from_df(self, df: pd.DataFrame):
        """
        Draws a metadata table from a 2-column DataFrame with consistent styling.

        Args:
            df (pd.DataFrame): A DataFrame with two columns: 'Label' and 'Value'
        """
        self.set_font("DejaVu", '', 16)
        self.set_fill_color(244, 246, 250)  # Light gray background

        label_width = 60
        value_width = self.w - 2 * self.l_margin - label_width

        for _, row in df.iterrows():
            label = str(row[0])
            value = str(row[1])

            self.set_font("DejaVu", 'B', 16)
            self.cell(label_width, 10, label, border=1, fill=True)
            self.set_font("DejaVu", '', 16)
            self.cell(value_width, 10, value, border=1)
            self.ln()

    def homepage(self, metatable_df=None):
        self.add_page()
        self.start_section(name=f"{self.report_title} Homepage", level=0)
        self.add_metadata_table_from_df(metatable_df)
        # Add image
        mascot_path = utils.get_asset_path("mascot.png")
        self.image(mascot_path, x=(self.w - 100)/2, y=150, w=100)  
        self.ln(95)
        self.set_font("Dejavu", 'B', 16)
        self.cell(0, 20, "\"Sniffing configs, one line at a time\"", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font("Dejavu", '', 16)
        self.cell(0, 10, f"KubeCase · https://github.com/kubecase/kubecase", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    def section_title(self, title: str):
        """
        Draw a consistent, styled section title.
        """     
        self.set_font("Dejavu", 'B', 16)
        self.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_paragraph(self, text, font_style='', font_size=12, spacing=5):
        self.set_font("Dejavu", font_style, font_size)
        self.write(spacing, text)
        self.ln()

    def add_color_legend(self, title, items, col_widths=(20, 100)):
        """
        Draws a two-column legend box.
        :param title: Title of the legend section (e.g. "Legend:")
        :param items: List of tuples → (fill_color as (R,G,B), label text)
        :param col_widths: Tuple of (color box width, label width)
        """
        self.set_font("Dejavu", "B", 11)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Dejavu", "", 10)

        color_w, label_w = col_widths
        for fill_color, label in items:
            self.set_fill_color(*fill_color)
            self.cell(color_w, 8, "", border=1, fill=True)
            self.set_fill_color(255, 255, 255)  # reset for next cell
            self.cell(label_w, 8, label, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def save_report(self, report_name: str, namespace: str, folder: str = "reports"):
        """
        Save the report PDF to a timestamped file path.

        Args:
            report_name (str): Type of report (e.g., 'pdb_report', 'probe_report')
            namespace (str): Namespace used in the report
            folder (str): Directory to save the PDF into (default: 'reports')
        """
        os.makedirs(folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{report_name}_{namespace}_{timestamp}.pdf"
        out_path = os.path.join(folder, filename)

        try:
            self.output(out_path)
            typer.echo(f"✅ KubeCase {report_name.replace('_', ' ').title()} saved to {out_path}")
        except Exception as e:
            typer.echo(f"❌ Error saving PDF: {e}")