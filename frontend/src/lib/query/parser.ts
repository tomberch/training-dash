/**
 * Recursive descent parser for the query DSL.
 * Converts tokens into an AST.
 */

import { Lexer, Token, TokenType, LexerError } from "./lexer";
import type {
  Query,
  Projection,
  AggExpr,
  GroupKey,
  OrderItem,
  Expr,
  Value,
  BinaryOp,
  NotOp,
  Comparison,
  Between,
  InList,
  NullCheck,
  TextMatch,
  BooleanField,
  NumberValue,
  StringValue,
  DateValue,
  RelativeDate,
  BoolValue,
  DurationValue,
} from "./types";

export class ParseError extends Error {
  constructor(
    public message: string,
    public position: number,
    public line: number,
    public column: number,
    public expected?: string[]
  ) {
    super(message);
    this.name = "ParseError";
  }

  getContext(input: string): string {
    const lines = input.split("\n");
    const line = lines[this.line - 1] || "";
    const pointer = " ".repeat(this.column - 1) + "^";
    return `${line}\n${pointer}`;
  }
}

const AGG_FUNCS = new Set(["COUNT", "SUM", "AVG", "MIN", "MAX"]);
const COMPARISON_OPS = new Set(["EQ", "NE", "GT", "GE", "LT", "LE"]);
const TIME_BUCKETS = new Set(["DAY", "WEEK", "MONTH", "YEAR"]);
const DATE_KEYWORDS = new Set([
  "NOW",
  "TODAY",
  "START_OF_DAY",
  "START_OF_WEEK",
  "START_OF_MONTH",
  "START_OF_YEAR",
]);

export class Parser {
  private tokens: Token[] = [];
  private pos = 0;
  private input: string;

  constructor(input: string) {
    this.input = input;
  }

  parse(): Query {
    const lexer = new Lexer(this.input);
    this.tokens = lexer.tokenize();
    this.pos = 0;

    const query = this.parseQuery();

    if (!this.isAtEnd()) {
      const token = this.peek();
      throw new ParseError(
        `Unexpected token: ${token.value}`,
        token.position,
        token.line,
        token.column
      );
    }

    return query;
  }

  private parseQuery(): Query {
    // Check if this is an aggregate query (starts with AGG_FUNC)
    if (this.isAggFunc(this.peek().type)) {
      return this.parseAggQuery();
    }
    return this.parseListQuery();
  }

  private parseListQuery(): Query {
    let projection: Projection | null = null;
    let conditions: Expr | null = null;
    let orderBy: OrderItem[] | null = null;
    let limit: number | null = null;

    // Handle different list query forms
    if (this.check("SELECT")) {
      this.advance(); // SELECT
      projection = this.parseProjection();
    }

    // Check for WHERE or bare expression
    if (this.check("WHERE")) {
      this.advance(); // WHERE
      conditions = this.parseExpr();
    } else if (
      !this.check("ORDER") &&
      !this.check("LIMIT") &&
      !this.isAtEnd() &&
      !this.check("STAR")
    ) {
      // Bare expression (no WHERE keyword)
      if (this.check("IDENTIFIER") || this.check("NOT") || this.check("LPAREN")) {
        conditions = this.parseExpr();
      }
    }

    // Handle * (all)
    if (this.check("STAR") && !projection && !conditions) {
      this.advance();
      projection = { kind: "all" };
    }

    // ORDER BY
    if (this.check("ORDER")) {
      this.advance(); // ORDER
      this.expect("BY");
      orderBy = this.parseOrderItems();
    }

    // LIMIT
    if (this.check("LIMIT")) {
      this.advance(); // LIMIT
      const limitToken = this.expect("INTEGER");
      limit = parseInt(limitToken.value, 10);
    }

    return {
      type: "list",
      projection,
      conditions,
      groupBy: null,
      orderBy,
      limit,
    };
  }

  private parseAggQuery(): Query {
    const aggregates = this.parseAggExprList();
    let conditions: Expr | null = null;
    let groupBy: GroupKey[] | null = null;

    // WHERE clause
    if (this.check("WHERE")) {
      this.advance();
      conditions = this.parseExpr();
    }

    // GROUP BY
    if (this.check("GROUP")) {
      this.advance(); // GROUP
      this.expect("BY");
      groupBy = this.parseGroupItems();
    }

    return {
      type: "aggregate",
      projection: { kind: "aggregates", aggregates },
      conditions,
      groupBy,
      orderBy: null,
      limit: null,
    };
  }

  private parseProjection(): Projection {
    if (this.check("STAR")) {
      this.advance();
      return { kind: "all" };
    }

    // View names
    if (
      this.check("SUMMARY") ||
      this.check("POWER") ||
      this.check("HR") ||
      this.check("FULL")
    ) {
      const view = this.advance().value.toLowerCase();
      return { kind: "view", view };
    }

    // Field list
    const fields = this.parseFieldList();
    return { kind: "fields", fields };
  }

  private parseFieldList(): string[] {
    const fields: string[] = [];
    fields.push(this.expect("IDENTIFIER").value);

    while (this.check("COMMA")) {
      this.advance();
      fields.push(this.expect("IDENTIFIER").value);
    }

    return fields;
  }

  private parseAggExprList(): AggExpr[] {
    const exprs: AggExpr[] = [];
    exprs.push(this.parseAggExpr());

    while (this.check("COMMA")) {
      this.advance();
      exprs.push(this.parseAggExpr());
    }

    return exprs;
  }

  private parseAggExpr(): AggExpr {
    const funcToken = this.advance();
    if (!this.isAggFunc(funcToken.type)) {
      throw new ParseError(
        `Expected aggregation function, got: ${funcToken.value}`,
        funcToken.position,
        funcToken.line,
        funcToken.column,
        ["COUNT", "SUM", "AVG", "MIN", "MAX"]
      );
    }

    this.expect("LPAREN");

    let field: string | null = null;
    if (this.check("STAR")) {
      this.advance();
    } else {
      field = this.expect("IDENTIFIER").value;
    }

    this.expect("RPAREN");

    return {
      func: funcToken.type as AggExpr["func"],
      field,
    };
  }

  private parseGroupItems(): GroupKey[] {
    const items: GroupKey[] = [];
    items.push(this.parseGroupItem());

    while (this.check("COMMA")) {
      this.advance();
      items.push(this.parseGroupItem());
    }

    return items;
  }

  private parseGroupItem(): GroupKey {
    const token = this.peek();

    if (TIME_BUCKETS.has(token.type)) {
      this.advance();
      return { kind: "time_bucket", value: token.value.toLowerCase() };
    }

    const field = this.expect("IDENTIFIER").value;
    return { kind: "field", value: field };
  }

  private parseOrderItems(): OrderItem[] {
    const items: OrderItem[] = [];
    items.push(this.parseOrderItem());

    while (this.check("COMMA")) {
      this.advance();
      items.push(this.parseOrderItem());
    }

    return items;
  }

  private parseOrderItem(): OrderItem {
    const field = this.expect("IDENTIFIER").value;
    let direction: "ASC" | "DESC" = "ASC";

    if (this.check("ASC")) {
      this.advance();
      direction = "ASC";
    } else if (this.check("DESC")) {
      this.advance();
      direction = "DESC";
    }

    return { field, direction };
  }

  // Expression parsing (precedence climbing)

  private parseExpr(): Expr {
    return this.parseOr();
  }

  private parseOr(): Expr {
    let left = this.parseAnd();

    while (this.check("OR")) {
      this.advance();
      const right = this.parseAnd();
      left = { type: "BinaryOp", op: "OR", left, right };
    }

    return left;
  }

  private parseAnd(): Expr {
    let left = this.parseNot();

    while (this.check("AND")) {
      this.advance();
      const right = this.parseNot();
      left = { type: "BinaryOp", op: "AND", left, right };
    }

    return left;
  }

  private parseNot(): Expr {
    if (this.check("NOT")) {
      this.advance();
      const expr = this.parseAtom();
      return { type: "NotOp", expr };
    }

    return this.parseAtom();
  }

  private parseAtom(): Expr {
    // Parenthesized expression
    if (this.check("LPAREN")) {
      this.advance();
      const expr = this.parseExpr();
      this.expect("RPAREN");
      return expr;
    }

    // Must be field-based expression
    const fieldToken = this.expect("IDENTIFIER");
    const field = fieldToken.value;

    // Check for various expression forms

    // NOT IN
    if (this.check("NOT")) {
      const notToken = this.advance();
      if (this.check("IN")) {
        this.advance();
        return this.parseInList(field, true);
      }
      // Backtrack - NOT was for something else
      this.pos--;
    }

    // IN
    if (this.check("IN")) {
      this.advance();
      return this.parseInList(field, false);
    }

    // BETWEEN
    if (this.check("BETWEEN")) {
      this.advance();
      return this.parseBetween(field);
    }

    // IS NULL / IS NOT NULL
    if (this.check("IS")) {
      this.advance();
      const negated = this.check("NOT");
      if (negated) this.advance();
      this.expect("NULL");
      return { type: "NullCheck", field, isNull: !negated };
    }

    // Text matching
    if (this.check("CONTAINS")) {
      this.advance();
      const valueToken = this.expect("STRING");
      return { type: "TextMatch", field, op: "CONTAINS", value: valueToken.value };
    }
    if (this.check("STARTS")) {
      this.advance();
      this.expect("WITH");
      const valueToken = this.expect("STRING");
      return { type: "TextMatch", field, op: "STARTS_WITH", value: valueToken.value };
    }
    if (this.check("ENDS")) {
      this.advance();
      this.expect("WITH");
      const valueToken = this.expect("STRING");
      return { type: "TextMatch", field, op: "ENDS_WITH", value: valueToken.value };
    }

    // Comparison operators
    if (this.isComparisonOp(this.peek().type)) {
      const opToken = this.advance();
      const value = this.parseValue();
      const op = this.tokenToCompOp(opToken.type);
      return { type: "Comparison", field, op, value };
    }

    // Standalone boolean field
    return { type: "BooleanField", field };
  }

  private parseInList(field: string, negated: boolean): InList {
    this.expect("LPAREN");
    const values: Value[] = [];
    values.push(this.parseValue());

    while (this.check("COMMA")) {
      this.advance();
      values.push(this.parseValue());
    }

    this.expect("RPAREN");
    return { type: "InList", field, values, negated };
  }

  private parseBetween(field: string): Between {
    const low = this.parseValue();
    this.expect("AND");
    const high = this.parseValue();
    return { type: "Between", field, low, high };
  }

  private parseValue(): Value {
    const token = this.peek();

    // Boolean
    if (token.type === "TRUE") {
      this.advance();
      return { type: "BoolValue", value: true };
    }
    if (token.type === "FALSE") {
      this.advance();
      return { type: "BoolValue", value: false };
    }

    // String
    if (token.type === "STRING") {
      this.advance();
      return { type: "StringValue", value: token.value };
    }

    // Date
    if (token.type === "DATE") {
      this.advance();
      return { type: "DateValue", value: new Date(token.value) };
    }

    // Duration (colon format)
    if (token.type === "DURATION") {
      this.advance();
      const seconds = this.parseDurationString(token.value);
      return { type: "DurationValue", seconds };
    }

    // Relative date keywords
    if (DATE_KEYWORDS.has(token.type)) {
      this.advance();
      const base = token.type as RelativeDate["base"];

      // Check for offset
      let offsetDays: number | null = null;
      if (this.check("PLUS") || this.check("MINUS")) {
        const sign = this.advance().type === "PLUS" ? 1 : -1;
        
        // Handle "30d" as a single token or "30 d" as separate tokens
        const token = this.peek();
        if (token.type === "NUMBER" || token.type === "INTEGER") {
          this.advance();
          const { value, unit } = this.parseNumberWithUnit(token.value);
          if (unit && ["d", "w", "mo", "y"].includes(unit)) {
            offsetDays = this.dateUnitToDays(value, unit) * sign;
          } else {
            offsetDays = value * sign;
          }
        }
      }

      return { type: "RelativeDate", base, offsetDays };
    }

    // Number with optional unit
    if (token.type === "NUMBER" || token.type === "INTEGER") {
      this.advance();
      const { value, unit } = this.parseNumberWithUnit(token.value);
      return { type: "NumberValue", value, unit };
    }

    throw new ParseError(
      `Expected value, got: ${token.value}`,
      token.position,
      token.line,
      token.column,
      ["number", "string", "date", "boolean"]
    );
  }

  private parseNumberWithUnit(str: string): { value: number; unit: string | null } {
    // Match number and optional unit
    const match = str.match(/^(-?\d+(?:\.\d+)?)(km|mi|m|ft|kph|mph|mps|h|min|sec|s|d|w|mo|y)?$/i);
    if (match) {
      return {
        value: parseFloat(match[1]),
        unit: match[2]?.toLowerCase() ?? null,
      };
    }
    return { value: parseFloat(str), unit: null };
  }

  private parseDurationString(str: string): number {
    // Format: H:MM:SS or MM:SS
    const parts = str.split(":").map((p) => parseInt(p, 10));
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    return 0;
  }

  private dateUnitToDays(value: number, unit: string): number {
    switch (unit) {
      case "d":
        return value;
      case "w":
        return value * 7;
      case "mo":
        return value * 30;
      case "y":
        return value * 365;
      default:
        return value;
    }
  }

  private tokenToCompOp(type: TokenType): Comparison["op"] {
    switch (type) {
      case "EQ":
        return "=";
      case "NE":
        return "!=";
      case "GT":
        return ">";
      case "GE":
        return ">=";
      case "LT":
        return "<";
      case "LE":
        return "<=";
      default:
        throw new Error(`Unknown comparison operator: ${type}`);
    }
  }

  // Helper methods

  private peek(): Token {
    return this.tokens[this.pos];
  }

  private advance(): Token {
    const token = this.tokens[this.pos];
    if (!this.isAtEnd()) this.pos++;
    return token;
  }

  private check(type: TokenType): boolean {
    return !this.isAtEnd() && this.peek().type === type;
  }

  private isAtEnd(): boolean {
    return this.peek().type === "EOF";
  }

  private expect(type: TokenType): Token {
    if (this.check(type)) {
      return this.advance();
    }
    const token = this.peek();
    throw new ParseError(
      `Expected ${type}, got: ${token.value}`,
      token.position,
      token.line,
      token.column,
      [type]
    );
  }

  private isAggFunc(type: TokenType): boolean {
    return AGG_FUNCS.has(type);
  }

  private isComparisonOp(type: TokenType): boolean {
    return COMPARISON_OPS.has(type);
  }
}

/**
 * Parse a query string into an AST.
 */
export function parse(input: string): Query {
  const parser = new Parser(input);
  return parser.parse();
}
