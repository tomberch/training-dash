import { describe, it, expect } from "vitest";
import { parse, ParseError } from "./parser";
import { Lexer, LexerError } from "./lexer";

describe("Lexer", () => {
  it("tokenizes simple comparison", () => {
    const lexer = new Lexer("tss > 100");
    const tokens = lexer.tokenize();
    expect(tokens.map((t) => t.type)).toEqual(["IDENTIFIER", "GT", "INTEGER", "EOF"]);
  });

  it("tokenizes keywords case-insensitively", () => {
    const lexer = new Lexer("WHERE TSS > 100 AND distance > 50km");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("WHERE");
    expect(tokens[4].type).toBe("AND");
  });

  it("tokenizes strings with escapes", () => {
    const lexer = new Lexer('"hello \\"world\\""');
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("STRING");
    expect(tokens[0].value).toBe('hello "world"');
  });

  it("tokenizes dates", () => {
    const lexer = new Lexer("2024-01-15");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("DATE");
    expect(tokens[0].value).toBe("2024-01-15");
  });

  it("tokenizes date with time", () => {
    const lexer = new Lexer("2024-01-15T10:30:00");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("DATE");
    expect(tokens[0].value).toBe("2024-01-15T10:30:00");
  });

  it("tokenizes duration in colon format", () => {
    const lexer = new Lexer("1:30:00");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("DURATION");
    expect(tokens[0].value).toBe("1:30:00");
  });

  it("tokenizes numbers with units", () => {
    const lexer = new Lexer("50km 30mph 2h");
    const tokens = lexer.tokenize();
    expect(tokens[0].value).toBe("50km");
    expect(tokens[1].value).toBe("30mph");
    expect(tokens[2].value).toBe("2h");
  });

  it("tokenizes aggregation functions", () => {
    const lexer = new Lexer("COUNT(*) AVG(tss)");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("COUNT");
    expect(tokens[4].type).toBe("AVG");
  });

  it("tokenizes relative date keywords", () => {
    const lexer = new Lexer("NOW TODAY START_OF_MONTH");
    const tokens = lexer.tokenize();
    expect(tokens[0].type).toBe("NOW");
    expect(tokens[1].type).toBe("TODAY");
    expect(tokens[2].type).toBe("START_OF_MONTH");
  });

  it("reports position on error", () => {
    const lexer = new Lexer("tss > @");
    expect(() => lexer.tokenize()).toThrow(LexerError);
  });
});


describe("Parser - List Queries", () => {
  it("parses simple comparison", () => {
    const ast = parse("tss > 100");
    expect(ast.type).toBe("list");
    expect(ast.conditions).toMatchObject({
      type: "Comparison",
      field: "tss",
      op: ">",
      value: { type: "NumberValue", value: 100 },
    });
  });

  it("parses comparison with unit", () => {
    const ast = parse("distance > 50km");
    expect(ast.conditions).toMatchObject({
      type: "Comparison",
      field: "distance",
      op: ">",
      value: { type: "NumberValue", value: 50, unit: "km" },
    });
  });

  it("parses WHERE clause", () => {
    const ast = parse("WHERE tss > 100");
    expect(ast.conditions).toMatchObject({
      type: "Comparison",
      field: "tss",
      op: ">",
    });
  });

  it("parses AND expression", () => {
    const ast = parse("tss > 100 AND distance > 50km");
    expect(ast.conditions).toMatchObject({
      type: "BinaryOp",
      op: "AND",
      left: { type: "Comparison", field: "tss" },
      right: { type: "Comparison", field: "distance" },
    });
  });

  it("parses OR expression", () => {
    const ast = parse("breakthrough = true OR tss > 200");
    expect(ast.conditions).toMatchObject({
      type: "BinaryOp",
      op: "OR",
    });
  });

  it("parses NOT expression", () => {
    const ast = parse("NOT breakthrough");
    expect(ast.conditions).toMatchObject({
      type: "NotOp",
      expr: { type: "BooleanField", field: "breakthrough" },
    });
  });

  it("parses parenthesized expression", () => {
    const ast = parse("(tss > 100 OR tss < 50) AND distance > 30km");
    expect(ast.conditions?.type).toBe("BinaryOp");
    expect((ast.conditions as any).op).toBe("AND");
    expect((ast.conditions as any).left.type).toBe("BinaryOp");
    expect((ast.conditions as any).left.op).toBe("OR");
  });

  it("parses IN expression", () => {
    const ast = parse('source IN ("xert", "garmin")');
    expect(ast.conditions).toMatchObject({
      type: "InList",
      field: "source",
      negated: false,
      values: [
        { type: "StringValue", value: "xert" },
        { type: "StringValue", value: "garmin" },
      ],
    });
  });

  it("parses NOT IN expression", () => {
    const ast = parse('source NOT IN ("upload")');
    expect(ast.conditions).toMatchObject({
      type: "InList",
      field: "source",
      negated: true,
    });
  });

  it("parses BETWEEN expression", () => {
    const ast = parse("tss BETWEEN 50 AND 150");
    expect(ast.conditions).toMatchObject({
      type: "Between",
      field: "tss",
      low: { type: "NumberValue", value: 50 },
      high: { type: "NumberValue", value: 150 },
    });
  });

  it("parses IS NULL", () => {
    const ast = parse("avg_power_w IS NULL");
    expect(ast.conditions).toMatchObject({
      type: "NullCheck",
      field: "avg_power_w",
      isNull: true,
    });
  });

  it("parses IS NOT NULL", () => {
    const ast = parse("avg_power_w IS NOT NULL");
    expect(ast.conditions).toMatchObject({
      type: "NullCheck",
      field: "avg_power_w",
      isNull: false,
    });
  });

  it("parses CONTAINS", () => {
    const ast = parse('title CONTAINS "climb"');
    expect(ast.conditions).toMatchObject({
      type: "TextMatch",
      field: "title",
      op: "CONTAINS",
      value: "climb",
    });
  });

  it("parses STARTS WITH", () => {
    const ast = parse('title STARTS WITH "Morning"');
    expect(ast.conditions).toMatchObject({
      type: "TextMatch",
      field: "title",
      op: "STARTS_WITH",
      value: "Morning",
    });
  });

  it("parses ENDS WITH", () => {
    const ast = parse('title ENDS WITH "Ride"');
    expect(ast.conditions).toMatchObject({
      type: "TextMatch",
      field: "title",
      op: "ENDS_WITH",
      value: "Ride",
    });
  });

  it("parses boolean field", () => {
    const ast = parse("breakthrough");
    expect(ast.conditions).toMatchObject({
      type: "BooleanField",
      field: "breakthrough",
    });
  });

  it("parses ORDER BY", () => {
    const ast = parse("tss > 100 ORDER BY tss DESC");
    expect(ast.orderBy).toEqual([{ field: "tss", direction: "DESC" }]);
  });

  it("parses multiple ORDER BY fields", () => {
    const ast = parse("tss > 100 ORDER BY date DESC, tss ASC");
    expect(ast.orderBy).toEqual([
      { field: "date", direction: "DESC" },
      { field: "tss", direction: "ASC" },
    ]);
  });

  it("parses LIMIT", () => {
    const ast = parse("tss > 100 LIMIT 10");
    expect(ast.limit).toBe(10);
  });

  it("parses ORDER BY with LIMIT", () => {
    const ast = parse("tss > 100 ORDER BY tss DESC LIMIT 5");
    expect(ast.orderBy).toEqual([{ field: "tss", direction: "DESC" }]);
    expect(ast.limit).toBe(5);
  });

  it("parses * (all)", () => {
    const ast = parse("*");
    expect(ast.projection).toMatchObject({ kind: "all" });
  });
});


describe("Parser - Aggregate Queries", () => {
  it("parses COUNT(*)", () => {
    const ast = parse("COUNT(*)");
    expect(ast.type).toBe("aggregate");
    expect(ast.projection).toMatchObject({
      kind: "aggregates",
      aggregates: [{ func: "COUNT", field: null }],
    });
  });

  it("parses AVG(field)", () => {
    const ast = parse("AVG(tss)");
    expect(ast.projection).toMatchObject({
      kind: "aggregates",
      aggregates: [{ func: "AVG", field: "tss" }],
    });
  });

  it("parses multiple aggregates", () => {
    const ast = parse("COUNT(*), AVG(tss), SUM(distance)");
    expect(ast.projection?.aggregates).toHaveLength(3);
    expect(ast.projection?.aggregates?.[0].func).toBe("COUNT");
    expect(ast.projection?.aggregates?.[1].func).toBe("AVG");
    expect(ast.projection?.aggregates?.[2].func).toBe("SUM");
  });

  it("parses aggregate with WHERE", () => {
    const ast = parse("AVG(tss) WHERE tss > 100");
    expect(ast.type).toBe("aggregate");
    expect(ast.conditions).toMatchObject({
      type: "Comparison",
      field: "tss",
    });
  });

  it("parses GROUP BY time bucket", () => {
    const ast = parse("COUNT(*) GROUP BY month");
    expect(ast.groupBy).toEqual([{ kind: "time_bucket", value: "month" }]);
  });

  it("parses GROUP BY field", () => {
    const ast = parse("COUNT(*) GROUP BY source");
    expect(ast.groupBy).toEqual([{ kind: "field", value: "source" }]);
  });

  it("parses GROUP BY multiple", () => {
    const ast = parse("COUNT(*) GROUP BY month, source");
    expect(ast.groupBy).toHaveLength(2);
    expect(ast.groupBy?.[0]).toEqual({ kind: "time_bucket", value: "month" });
    expect(ast.groupBy?.[1]).toEqual({ kind: "field", value: "source" });
  });

  it("parses full aggregate query", () => {
    const ast = parse("COUNT(*), AVG(tss) WHERE tss > 50 GROUP BY month");
    expect(ast.type).toBe("aggregate");
    expect(ast.projection?.aggregates).toHaveLength(2);
    expect(ast.conditions).not.toBeNull();
    expect(ast.groupBy).toHaveLength(1);
  });
});

describe("Parser - Values", () => {
  it("parses integer", () => {
    const ast = parse("tss = 100");
    expect((ast.conditions as any).value).toMatchObject({
      type: "NumberValue",
      value: 100,
      unit: null,
    });
  });

  it("parses float", () => {
    const ast = parse("intensity_factor = 0.85");
    expect((ast.conditions as any).value).toMatchObject({
      type: "NumberValue",
      value: 0.85,
    });
  });

  it("parses string", () => {
    const ast = parse('source = "xert"');
    expect((ast.conditions as any).value).toMatchObject({
      type: "StringValue",
      value: "xert",
    });
  });

  it("parses single-quoted string", () => {
    const ast = parse("source = 'garmin'");
    expect((ast.conditions as any).value).toMatchObject({
      type: "StringValue",
      value: "garmin",
    });
  });

  it("parses boolean true", () => {
    const ast = parse("breakthrough = true");
    expect((ast.conditions as any).value).toMatchObject({
      type: "BoolValue",
      value: true,
    });
  });

  it("parses boolean false", () => {
    const ast = parse("breakthrough = false");
    expect((ast.conditions as any).value).toMatchObject({
      type: "BoolValue",
      value: false,
    });
  });

  it("parses date", () => {
    const ast = parse("date >= 2024-01-01");
    expect((ast.conditions as any).value.type).toBe("DateValue");
  });

  it("parses duration in colon format", () => {
    const ast = parse("duration > 1:30:00");
    expect((ast.conditions as any).value).toMatchObject({
      type: "DurationValue",
      seconds: 5400, // 1.5 hours
    });
  });

  it("parses relative date NOW", () => {
    const ast = parse("date >= NOW");
    expect((ast.conditions as any).value).toMatchObject({
      type: "RelativeDate",
      base: "NOW",
      offsetDays: null,
    });
  });

  it("parses relative date with offset", () => {
    const ast = parse("date >= NOW - 30d");
    expect((ast.conditions as any).value).toMatchObject({
      type: "RelativeDate",
      base: "NOW",
      offsetDays: -30,
    });
  });

  it("parses START_OF_MONTH", () => {
    const ast = parse("date >= START_OF_MONTH");
    expect((ast.conditions as any).value).toMatchObject({
      type: "RelativeDate",
      base: "START_OF_MONTH",
    });
  });
});

describe("Parser - Error Handling", () => {
  it("reports unexpected token", () => {
    expect(() => parse("tss > > 100")).toThrow(ParseError);
  });

  it("reports unclosed parenthesis", () => {
    expect(() => parse("(tss > 100")).toThrow(ParseError);
  });

  it("includes position in error", () => {
    try {
      parse("tss > @invalid");
    } catch (e) {
      expect(e).toBeInstanceOf(LexerError);
      expect((e as LexerError).position).toBeGreaterThan(0);
    }
  });

  it("provides context for error", () => {
    try {
      parse("tss > > 100");
    } catch (e) {
      expect(e).toBeInstanceOf(ParseError);
      const ctx = (e as ParseError).getContext("tss > > 100");
      expect(ctx).toContain("^");
    }
  });
});

describe("Parser - Edge Cases", () => {
  it("handles extra whitespace", () => {
    const ast = parse("  tss   >   100  ");
    expect(ast.conditions).toMatchObject({
      type: "Comparison",
      field: "tss",
    });
  });

  it("handles case-insensitive keywords", () => {
    const ast = parse("TSS > 100 and DISTANCE > 50km");
    expect(ast.conditions?.type).toBe("BinaryOp");
  });

  it("handles complex nested expression", () => {
    const ast = parse(
      "(tss > 100 AND distance > 50km) OR (breakthrough = true AND source = 'xert')"
    );
    expect(ast.conditions?.type).toBe("BinaryOp");
    expect((ast.conditions as any).op).toBe("OR");
  });

  it("handles all comparison operators", () => {
    const ops = ["=", "!=", ">", ">=", "<", "<="];
    for (const op of ops) {
      const ast = parse(`tss ${op} 100`);
      expect((ast.conditions as any).op).toBe(op);
    }
  });

  it("handles all aggregation functions", () => {
    const funcs = ["COUNT", "SUM", "AVG", "MIN", "MAX"];
    for (const func of funcs) {
      const ast = parse(`${func}(tss)`);
      expect(ast.projection?.aggregates?.[0].func).toBe(func);
    }
  });

  it("handles all time buckets", () => {
    const buckets = ["day", "week", "month", "year"];
    for (const bucket of buckets) {
      const ast = parse(`COUNT(*) GROUP BY ${bucket}`);
      expect(ast.groupBy?.[0].value).toBe(bucket);
    }
  });
});
