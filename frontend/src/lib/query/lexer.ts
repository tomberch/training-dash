/**
 * Lexer/tokenizer for the query DSL.
 * Converts input text into a stream of tokens.
 */

export type TokenType =
  // Keywords
  | "SELECT"
  | "WHERE"
  | "ORDER"
  | "BY"
  | "GROUP"
  | "LIMIT"
  | "AND"
  | "OR"
  | "NOT"
  | "IN"
  | "BETWEEN"
  | "IS"
  | "NULL"
  | "ASC"
  | "DESC"
  | "TRUE"
  | "FALSE"
  // Text operators
  | "CONTAINS"
  | "STARTS"
  | "ENDS"
  | "WITH"
  // Date keywords
  | "NOW"
  | "TODAY"
  | "START_OF_DAY"
  | "START_OF_WEEK"
  | "START_OF_MONTH"
  | "START_OF_YEAR"
  // View names
  | "SUMMARY"
  | "POWER"
  | "HR"
  | "FULL"
  // Time buckets
  | "DAY"
  | "WEEK"
  | "MONTH"
  | "YEAR"
  // Aggregation functions
  | "COUNT"
  | "SUM"
  | "AVG"
  | "MIN"
  | "MAX"
  // Operators
  | "EQ"
  | "NE"
  | "GT"
  | "GE"
  | "LT"
  | "LE"
  | "PLUS"
  | "MINUS"
  // Literals
  | "NUMBER"
  | "INTEGER"
  | "STRING"
  | "DATE"
  | "TIME"
  | "DURATION"
  // Units
  | "DISTANCE_UNIT"
  | "SPEED_UNIT"
  | "DURATION_UNIT"
  | "DATE_UNIT"
  // Identifiers and special
  | "IDENTIFIER"
  | "STAR"
  | "LPAREN"
  | "RPAREN"
  | "COMMA"
  | "EOF";

export interface Token {
  type: TokenType;
  value: string;
  position: number;
  line: number;
  column: number;
}

export class LexerError extends Error {
  constructor(
    message: string,
    public position: number,
    public line: number,
    public column: number
  ) {
    super(message);
    this.name = "LexerError";
  }
}

// Keywords (case-insensitive)
const KEYWORDS: Record<string, TokenType> = {
  select: "SELECT",
  where: "WHERE",
  order: "ORDER",
  by: "BY",
  group: "GROUP",
  limit: "LIMIT",
  and: "AND",
  or: "OR",
  not: "NOT",
  in: "IN",
  between: "BETWEEN",
  is: "IS",
  null: "NULL",
  asc: "ASC",
  desc: "DESC",
  true: "TRUE",
  false: "FALSE",
  contains: "CONTAINS",
  starts: "STARTS",
  ends: "ENDS",
  with: "WITH",
  now: "NOW",
  today: "TODAY",
  start_of_day: "START_OF_DAY",
  start_of_week: "START_OF_WEEK",
  start_of_month: "START_OF_MONTH",
  start_of_year: "START_OF_YEAR",
  summary: "SUMMARY",
  power: "POWER",
  hr: "HR",
  full: "FULL",
  day: "DAY",
  week: "WEEK",
  month: "MONTH",
  year: "YEAR",
  count: "COUNT",
  sum: "SUM",
  avg: "AVG",
  min: "MIN",
  max: "MAX",
};

// Unit patterns
const DISTANCE_UNITS = new Set(["km", "mi", "m", "ft"]);
const SPEED_UNITS = new Set(["kph", "mph", "mps"]);
const DURATION_UNITS = new Set(["h", "min", "sec", "s"]);
const DATE_UNITS = new Set(["d", "w", "mo", "y"]);

export class Lexer {
  private input: string;
  private pos = 0;
  private line = 1;
  private column = 1;

  constructor(input: string) {
    this.input = input;
  }

  tokenize(): Token[] {
    const tokens: Token[] = [];

    while (this.pos < this.input.length) {
      this.skipWhitespace();
      if (this.pos >= this.input.length) break;

      const token = this.nextToken();
      if (token) {
        tokens.push(token);
      }
    }

    tokens.push(this.makeToken("EOF", ""));
    return tokens;
  }

  private skipWhitespace(): void {
    while (this.pos < this.input.length) {
      const ch = this.input[this.pos];
      if (ch === " " || ch === "\t" || ch === "\r") {
        this.advance();
      } else if (ch === "\n") {
        this.advance();
        this.line++;
        this.column = 1;
      } else {
        break;
      }
    }
  }

  private advance(): string {
    const ch = this.input[this.pos];
    this.pos++;
    this.column++;
    return ch;
  }

  private peek(offset = 0): string {
    return this.input[this.pos + offset] ?? "";
  }

  private makeToken(type: TokenType, value: string): Token {
    return {
      type,
      value,
      position: this.pos - value.length,
      line: this.line,
      column: this.column - value.length,
    };
  }

  private nextToken(): Token | null {
    const startPos = this.pos;
    const startLine = this.line;
    const startCol = this.column;
    const ch = this.peek();

    // Single character tokens
    if (ch === "*") {
      this.advance();
      return { type: "STAR", value: "*", position: startPos, line: startLine, column: startCol };
    }
    if (ch === "(") {
      this.advance();
      return { type: "LPAREN", value: "(", position: startPos, line: startLine, column: startCol };
    }
    if (ch === ")") {
      this.advance();
      return { type: "RPAREN", value: ")", position: startPos, line: startLine, column: startCol };
    }
    if (ch === ",") {
      this.advance();
      return { type: "COMMA", value: ",", position: startPos, line: startLine, column: startCol };
    }
    if (ch === "+") {
      this.advance();
      return { type: "PLUS", value: "+", position: startPos, line: startLine, column: startCol };
    }
    if (ch === "-" && !this.isDigit(this.peek(1))) {
      this.advance();
      return { type: "MINUS", value: "-", position: startPos, line: startLine, column: startCol };
    }

    // Operators
    if (ch === "=") {
      this.advance();
      return { type: "EQ", value: "=", position: startPos, line: startLine, column: startCol };
    }
    if (ch === "!" && this.peek(1) === "=") {
      this.advance();
      this.advance();
      return { type: "NE", value: "!=", position: startPos, line: startLine, column: startCol };
    }
    if (ch === ">") {
      this.advance();
      if (this.peek() === "=") {
        this.advance();
        return { type: "GE", value: ">=", position: startPos, line: startLine, column: startCol };
      }
      return { type: "GT", value: ">", position: startPos, line: startLine, column: startCol };
    }
    if (ch === "<") {
      this.advance();
      if (this.peek() === "=") {
        this.advance();
        return { type: "LE", value: "<=", position: startPos, line: startLine, column: startCol };
      }
      return { type: "LT", value: "<", position: startPos, line: startLine, column: startCol };
    }

    // Strings
    if (ch === '"' || ch === "'") {
      return this.readString(ch);
    }

    // Numbers and dates
    if (this.isDigit(ch) || (ch === "-" && this.isDigit(this.peek(1)))) {
      return this.readNumberOrDate();
    }

    // Identifiers and keywords
    if (this.isIdentifierStart(ch)) {
      return this.readIdentifier();
    }

    throw new LexerError(
      `Unexpected character: '${ch}'`,
      this.pos,
      this.line,
      this.column
    );
  }

  private readString(quote: string): Token {
    const startPos = this.pos;
    const startLine = this.line;
    const startCol = this.column;

    this.advance(); // skip opening quote
    let value = "";

    while (this.pos < this.input.length) {
      const ch = this.peek();
      if (ch === quote) {
        this.advance(); // skip closing quote
        return { type: "STRING", value, position: startPos, line: startLine, column: startCol };
      }
      if (ch === "\\") {
        this.advance();
        const escaped = this.advance();
        if (escaped === "n") value += "\n";
        else if (escaped === "t") value += "\t";
        else value += escaped;
      } else {
        value += this.advance();
      }
    }

    throw new LexerError("Unterminated string", startPos, startLine, startCol);
  }

  private readNumberOrDate(): Token {
    const startPos = this.pos;
    const startLine = this.line;
    const startCol = this.column;

    // Check for date pattern: YYYY-MM-DD
    if (this.matchDate()) {
      const dateStr = this.input.slice(startPos, this.pos);

      // Check for time suffix
      if (this.peek() === "T" && this.isDigit(this.peek(1))) {
        const timeStart = this.pos;
        this.advance(); // T
        // Read time: HH:MM:SS
        while (this.isDigit(this.peek()) || this.peek() === ":") {
          this.advance();
        }
        const fullValue = this.input.slice(startPos, this.pos);
        return { type: "DATE", value: fullValue, position: startPos, line: startLine, column: startCol };
      }

      return { type: "DATE", value: dateStr, position: startPos, line: startLine, column: startCol };
    }

    // Read number (including potential duration like 1:30:00)
    let value = "";
    let colonCount = 0;

    // Handle negative sign
    if (this.peek() === "-") {
      value += this.advance();
    }

    // Read digits and colons
    while (this.pos < this.input.length) {
      const ch = this.peek();
      if (this.isDigit(ch)) {
        value += this.advance();
      } else if (ch === "." && this.isDigit(this.peek(1)) && colonCount === 0) {
        value += this.advance();
      } else if (ch === ":" && this.isDigit(this.peek(1))) {
        value += this.advance();
        colonCount++;
      } else {
        break;
      }
    }

    // If we have colons, it's a duration
    if (colonCount > 0) {
      return { type: "DURATION", value, position: startPos, line: startLine, column: startCol };
    }

    // Check for unit suffix
    const unitStart = this.pos;
    let unitValue = "";
    while (this.isLetter(this.peek())) {
      unitValue += this.advance();
    }

    if (unitValue) {
      const unitLower = unitValue.toLowerCase();
      if (DISTANCE_UNITS.has(unitLower)) {
        return { type: "NUMBER", value: value + unitValue, position: startPos, line: startLine, column: startCol };
      }
      if (SPEED_UNITS.has(unitLower)) {
        return { type: "NUMBER", value: value + unitValue, position: startPos, line: startLine, column: startCol };
      }
      if (DURATION_UNITS.has(unitLower)) {
        return { type: "NUMBER", value: value + unitValue, position: startPos, line: startLine, column: startCol };
      }
      if (DATE_UNITS.has(unitLower)) {
        return { type: "NUMBER", value: value + unitValue, position: startPos, line: startLine, column: startCol };
      }
      // Unknown unit - backtrack and return just the number
      this.pos = unitStart;
      this.column = startCol + value.length;
    }

    // Check if it's an integer
    const isInteger = !value.includes(".");
    return {
      type: isInteger ? "INTEGER" : "NUMBER",
      value,
      position: startPos,
      line: startLine,
      column: startCol,
    };
  }

  private matchDate(): boolean {
    // YYYY-MM-DD pattern
    const pattern = /^\d{4}-\d{2}-\d{2}/;
    const remaining = this.input.slice(this.pos);
    const match = pattern.exec(remaining);
    if (match) {
      this.pos += match[0].length;
      this.column += match[0].length;
      return true;
    }
    return false;
  }

  private readIdentifier(): Token {
    const startPos = this.pos;
    const startLine = this.line;
    const startCol = this.column;

    let value = "";
    while (this.pos < this.input.length && this.isIdentifierChar(this.peek())) {
      value += this.advance();
    }

    // Check for keyword
    const lower = value.toLowerCase();
    const keywordType = KEYWORDS[lower];
    if (keywordType) {
      return { type: keywordType, value: value.toUpperCase(), position: startPos, line: startLine, column: startCol };
    }

    return { type: "IDENTIFIER", value, position: startPos, line: startLine, column: startCol };
  }

  private isDigit(ch: string): boolean {
    return ch >= "0" && ch <= "9";
  }

  private isLetter(ch: string): boolean {
    return (ch >= "a" && ch <= "z") || (ch >= "A" && ch <= "Z");
  }

  private isIdentifierStart(ch: string): boolean {
    return this.isLetter(ch) || ch === "_";
  }

  private isIdentifierChar(ch: string): boolean {
    return this.isLetter(ch) || this.isDigit(ch) || ch === "_";
  }
}
