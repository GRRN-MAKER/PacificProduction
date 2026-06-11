"""PACIFIC — Terminal-grade math rendering.

Converts raw LaTeX / KaTeX math expressions into clean Unicode text
suitable for Rich terminal display.  Block equations ($$…$$) get
rendered inside a styled Rich Panel; inline equations ($…$) are
converted in-place.

This is NOT a full TeX parser — it covers the subset commonly
produced by financial LLMs: fractions, Greek letters, superscripts,
subscripts, sums, integrals, matrices, common operators, and
standard finance notation.
"""

import re
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
#  Unicode symbol tables
# ═══════════════════════════════════════════════════════════════════════

GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\vartheta": "ϑ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ",
    r"\pi": "π", r"\varpi": "ϖ", r"\rho": "ρ", r"\varrho": "ϱ",
    r"\sigma": "σ", r"\varsigma": "ς", r"\tau": "τ", r"\upsilon": "υ",
    r"\phi": "φ", r"\varphi": "ϕ", r"\chi": "χ", r"\psi": "ψ",
    r"\omega": "ω",
    # Uppercase
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
}

OPERATORS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±",
    r"\mp": "∓", r"\leq": "≤", r"\geq": "≥", r"\neq": "≠",
    r"\approx": "≈", r"\equiv": "≡", r"\sim": "∼", r"\propto": "∝",
    r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇",
    r"\forall": "∀", r"\exists": "∃", r"\in": "∈", r"\notin": "∉",
    r"\subset": "⊂", r"\supset": "⊃", r"\subseteq": "⊆", r"\supseteq": "⊇",
    r"\cup": "∪", r"\cap": "∩", r"\emptyset": "∅",
    r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\Rightarrow": "⇒", r"\Leftarrow": "⇐", r"\Leftrightarrow": "⇔",
    r"\ldots": "…", r"\cdots": "⋯", r"\vdots": "⋮", r"\ddots": "⋱",
    r"\star": "⋆", r"\circ": "∘", r"\bullet": "•",
    r"\prime": "′", r"\dagger": "†",
}

FUNCTIONS = {
    r"\ln": "ln", r"\log": "log", r"\exp": "exp",
    r"\sin": "sin", r"\cos": "cos", r"\tan": "tan",
    r"\arcsin": "arcsin", r"\arccos": "arccos", r"\arctan": "arctan",
    r"\sinh": "sinh", r"\cosh": "cosh", r"\tanh": "tanh",
    r"\max": "max", r"\min": "min", r"\sup": "sup", r"\inf": "inf",
    r"\lim": "lim", r"\det": "det", r"\dim": "dim",
    r"\arg": "arg", r"\mod": "mod",
}

ACCENTS = {
    r"\hat": "̂", r"\bar": "̄", r"\tilde": "̃", r"\dot": "̇",
    r"\ddot": "̈", r"\vec": "⃗",
}

SUPERSCRIPTS = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ", "T": "ᵀ", "t": "ᵗ",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "j": "ʲ", "k": "ᵏ",
    "l": "ˡ", "m": "ᵐ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ",
    "s": "ˢ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ",
    "y": "ʸ", "z": "ᶻ",
    "*": "✱",
}

SUBSCRIPTS = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
}

BRACKETS = {
    r"\left(": "(", r"\right)": ")",
    r"\left[": "[", r"\right]": "]",
    r"\left\{": "{", r"\right\}": "}",
    r"\left|": "|", r"\right|": "|",
    r"\left\|": "‖", r"\right\|": "‖",
    r"\langle": "⟨", r"\rangle": "⟩",
    r"\lceil": "⌈", r"\rceil": "⌉",
    r"\lfloor": "⌊", r"\rfloor": "⌋",
    r"\{": "{", r"\}": "}",
}

MISC = {
    r"\quad": "  ", r"\qquad": "    ",
    r"\,": " ", r"\;": " ", r"\!": "",
    r"\text": "", r"\textrm": "", r"\textbf": "",
    r"\mathrm": "", r"\mathbf": "", r"\mathbb": "",
    r"\mathcal": "", r"\boldsymbol": "",
    r"\operatorname": "",
    r"\top": "ᵀ",
    r"\transpose": "ᵀ",
    r"\ell": "ℓ",
    r"\hbar": "ℏ",
    r"\Re": "ℜ", r"\Im": "ℑ",
}

# Bold math letters → standard (we don't have bold Unicode math easily)
MATHBB = {
    "R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ",
    "E": "𝔼", "P": "ℙ",
}


# ═══════════════════════════════════════════════════════════════════════
#  Core LaTeX → Unicode converter
# ═══════════════════════════════════════════════════════════════════════

def _strip_braces(s: str) -> str:
    """Remove one level of surrounding { }."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        return s[1:-1]
    return s


def _convert_superscript(text: str) -> str:
    """Convert ^{...} or ^x to Unicode superscripts."""
    def _sup_repl(m):
        content = _strip_braces(m.group(1))
        # Recursively convert inner LaTeX first
        content = _latex_to_unicode(content)
        return "".join(SUPERSCRIPTS.get(c, c) for c in content)

    # ^{...} form
    text = re.sub(r"\^\{([^}]*)\}", _sup_repl, text)
    # ^single_char form
    text = re.sub(r"\^([a-zA-Z0-9+\-*])", _sup_repl, text)
    return text


def _convert_subscript(text: str) -> str:
    """Convert _{...} or _x to Unicode subscripts."""
    def _sub_repl(m):
        content = _strip_braces(m.group(1))
        content = _latex_to_unicode(content)
        return "".join(SUBSCRIPTS.get(c, c) for c in content)

    # _{...} form
    text = re.sub(r"_\{([^}]*)\}", _sub_repl, text)
    # _single_char form
    text = re.sub(r"_([a-zA-Z0-9])", _sub_repl, text)
    return text


def _convert_frac(text: str) -> str:
    r"""Convert \frac{a}{b} to a/b or (a)/(b) for complex expressions."""
    def _frac_repl(m):
        num = _strip_braces(m.group(1))
        den = _strip_braces(m.group(2))
        num = _latex_to_unicode(num)
        den = _latex_to_unicode(den)
        # Simple fractions: single-char / single-char
        if len(num) <= 3 and len(den) <= 3:
            return f"{num}/{den}"
        return f"({num}) / ({den})"

    # Match \frac{...}{...} — handle nested braces up to 1 level
    pattern = r"\\frac\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
    prev = None
    while prev != text:
        prev = text
        text = re.sub(pattern, _frac_repl, text)
    return text


def _convert_sqrt(text: str) -> str:
    r"""Convert \sqrt{...} or \sqrt[n]{...} to Unicode."""
    def _sqrt_repl(m):
        index = m.group(1)
        content = _strip_braces(m.group(2))
        content = _latex_to_unicode(content)
        if index:
            idx = "".join(SUPERSCRIPTS.get(c, c) for c in index)
            return f"{idx}√({content})"
        return f"√({content})"

    text = re.sub(r"\\sqrt(?:\[([^\]]*)\])?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", _sqrt_repl, text)
    return text


def _convert_sum_prod_int(text: str) -> str:
    r"""Convert \sum, \prod, \int with limits."""
    replacements = {
        r"\sum": "∑", r"\prod": "∏",
        r"\int": "∫", r"\iint": "∬", r"\iiint": "∭",
        r"\oint": "∮",
    }
    for cmd, sym in replacements.items():
        text = text.replace(cmd, sym)
    return text


def _convert_mathbb(text: str) -> str:
    r"""Convert \mathbb{R} → ℝ, etc."""
    def _bb_repl(m):
        letter = m.group(1)
        return MATHBB.get(letter, letter)

    text = re.sub(r"\\mathbb\{([A-Z])\}", _bb_repl, text)
    return text


def _convert_accent(text: str) -> str:
    r"""Convert \hat{x} → x̂, \bar{x} → x̄, etc."""
    for cmd, combining in ACCENTS.items():
        def _acc_repl(m, comb=combining):
            content = _strip_braces(m.group(1))
            return content + comb

        text = re.sub(re.escape(cmd) + r"\{([^{}]*)\}", _acc_repl, text)
    return text


def _convert_text_commands(text: str) -> str:
    r"""Convert \text{...}, \mathrm{...}, etc. to plain text."""
    for cmd in (r"\text", r"\textrm", r"\textbf", r"\mathrm",
                r"\mathbf", r"\mathcal", r"\boldsymbol",
                r"\operatorname"):
        pattern = re.escape(cmd) + r"\{([^{}]*)\}"
        text = re.sub(pattern, r"\1", text)
    return text


def _latex_to_unicode(expr: str) -> str:
    """Convert a single LaTeX math expression to Unicode."""
    if not expr:
        return expr

    # Remove \displaystyle, \scriptstyle etc.
    expr = re.sub(r"\\(?:display|script|scriptscript)style\b", "", expr)

    # Text commands first (before Greek replacement eats \text)
    expr = _convert_text_commands(expr)

    # Fractions (before super/subscripts)
    expr = _convert_frac(expr)

    # Square roots
    expr = _convert_sqrt(expr)

    # mathbb
    expr = _convert_mathbb(expr)

    # Accents
    expr = _convert_accent(expr)

    # Sum/prod/int
    expr = _convert_sum_prod_int(expr)

    # Greek letters (longest first to avoid partial matches)
    for cmd in sorted(GREEK.keys(), key=len, reverse=True):
        expr = expr.replace(cmd, GREEK[cmd])

    # Operators
    for cmd in sorted(OPERATORS.keys(), key=len, reverse=True):
        expr = expr.replace(cmd, OPERATORS[cmd])

    # Functions
    for cmd in sorted(FUNCTIONS.keys(), key=len, reverse=True):
        expr = expr.replace(cmd, FUNCTIONS[cmd])

    # Brackets
    for cmd in sorted(BRACKETS.keys(), key=len, reverse=True):
        expr = expr.replace(cmd, BRACKETS[cmd])

    # Misc
    for cmd in sorted(MISC.keys(), key=len, reverse=True):
        expr = expr.replace(cmd, MISC[cmd])

    # Super/subscripts (after symbol replacement)
    expr = _convert_superscript(expr)
    expr = _convert_subscript(expr)

    # Clean up leftover braces
    expr = expr.replace("{", "").replace("}", "")

    # Collapse multiple spaces
    expr = re.sub(r"  +", " ", expr).strip()

    return expr


# ═══════════════════════════════════════════════════════════════════════
#  Public API — process full markdown text
# ═══════════════════════════════════════════════════════════════════════

def render_math(text: str) -> str:
    """Convert all LaTeX math in a markdown string to Unicode.

    Handles:
      - Block equations:  $$ ... $$  →  indented, boxed line
      - Inline equations: $ ... $    →  in-place Unicode
    """
    if not text:
        return text

    # ── Block equations: $$…$$ (possibly multiline) ──
    def _block_repl(m):
        raw = m.group(1).strip()
        # Join multiline into single expression
        raw = " ".join(raw.split())
        rendered = _latex_to_unicode(raw)
        # Wrap in a visible box for the terminal
        bar = "─" * min(len(rendered) + 4, 72)
        return f"\n  ┌{bar}┐\n  │  {rendered}  │\n  └{bar}┘\n"

    text = re.sub(r"\$\$(.*?)\$\$", _block_repl, text, flags=re.DOTALL)

    # ── Inline equations: $…$ (single-line only) ──
    def _inline_repl(m):
        raw = m.group(1).strip()
        return _latex_to_unicode(raw)

    # Negative lookbehind/ahead to avoid matching $$ or currency like $100
    text = re.sub(r"(?<!\$)\$(?!\$)(?!\d)(.+?)(?<!\$)\$(?!\$)", _inline_repl, text)

    return text


def render_code_blocks(text: str) -> str:
    """Enhance code blocks for terminal display — add language labels."""
    def _code_repl(m):
        lang = m.group(1) or ""
        code = m.group(2)
        label = f"  ╭── {lang.upper()} " if lang else "  ╭── CODE "
        label += "─" * max(0, 60 - len(label))
        return f"\n{label}╮\n```{lang}\n{code}\n```\n  ╰{'─' * 60}╯\n"

    text = re.sub(r"```(\w*)\n(.*?)```", _code_repl, text, flags=re.DOTALL)
    return text


def format_response(text: str) -> str:
    """Full pipeline: render math + enhance code in a response string."""
    text = render_math(text)
    return text
