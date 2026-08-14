/**
 * AST type definitions for the query DSL.
 * Mirrors the backend Python AST for consistency.
 */

// === Top Level ===

export interface Query {
  type: "list" | "aggregate";
  projection: Projection | null;
  conditions: Expr | null;
  groupBy: GroupKey[] | null;
  orderBy: OrderItem[] | null;
  limit: number | null;
}

// === Projection ===

export interface Projection {
  kind: "all" | "view" | "fields" | "aggregates";
  view?: string; // "summary", "power", "hr", "full"
  fields?: string[];
  aggregates?: AggExpr[];
}

export interface AggExpr {
  func: "COUNT" | "SUM" | "AVG" | "MIN" | "MAX";
  field: string | null; // null for COUNT(*)
}

export interface GroupKey {
  kind: "time_bucket" | "field";
  value: string; // "month", "week", etc. or field name
}

export interface OrderItem {
  field: string;
  direction: "ASC" | "DESC";
}

// === Expressions ===

export interface BinaryOp {
  type: "BinaryOp";
  op: "AND" | "OR";
  left: Expr;
  right: Expr;
}

export interface NotOp {
  type: "NotOp";
  expr: Expr;
}

export interface Comparison {
  type: "Comparison";
  field: string;
  op: "=" | "!=" | ">" | ">=" | "<" | "<=";
  value: Value;
}

export interface Between {
  type: "Between";
  field: string;
  low: Value;
  high: Value;
}

export interface InList {
  type: "InList";
  field: string;
  values: Value[];
  negated: boolean;
}

export interface NullCheck {
  type: "NullCheck";
  field: string;
  isNull: boolean;
}

export interface TextMatch {
  type: "TextMatch";
  field: string;
  op: "CONTAINS" | "STARTS_WITH" | "ENDS_WITH";
  value: string;
}

export interface BooleanField {
  type: "BooleanField";
  field: string;
}

export type Expr =
  | BinaryOp
  | NotOp
  | Comparison
  | Between
  | InList
  | NullCheck
  | TextMatch
  | BooleanField;

// === Values ===

export interface NumberValue {
  type: "NumberValue";
  value: number;
  unit: string | null;
}

export interface StringValue {
  type: "StringValue";
  value: string;
}

export interface DateValue {
  type: "DateValue";
  value: Date;
}

export interface RelativeDate {
  type: "RelativeDate";
  base:
    | "NOW"
    | "TODAY"
    | "START_OF_DAY"
    | "START_OF_WEEK"
    | "START_OF_MONTH"
    | "START_OF_YEAR";
  offsetDays: number | null;
}

export interface BoolValue {
  type: "BoolValue";
  value: boolean;
}

export interface DurationValue {
  type: "DurationValue";
  seconds: number;
}

export type Value =
  | NumberValue
  | StringValue
  | DateValue
  | RelativeDate
  | BoolValue
  | DurationValue;
