import assert from 'node:assert/strict';
import { test } from 'node:test';
import { escapeCsvValue, jsonToCsv, parseCsv, safeColumnName, toCsv } from '../src/util/csv.js';

test('escapes CSV values that contain delimiters, quotes or newlines', () => {
  assert.equal(escapeCsvValue('plain'), 'plain');
  assert.equal(escapeCsvValue('a,b'), '"a,b"');
  assert.equal(escapeCsvValue('say "hi"'), '"say ""hi"""');
  assert.equal(escapeCsvValue('line1\nline2'), '"line1\nline2"');
  assert.equal(escapeCsvValue(null), '');
  assert.equal(escapeCsvValue({ a: 1 }), '"{""a"":1}"');
});

test('toCsv and parseCsv round-trip awkward values', () => {
  const rows = [
    { id: 1, note: 'comma, inside' },
    { id: 2, note: 'quote " inside' },
    { id: 3, note: 'multi\nline' },
  ];
  const parsed = parseCsv(toCsv(rows, ['id', 'note']));
  assert.deepEqual(parsed, [
    ['id', 'note'],
    ['1', 'comma, inside'],
    ['2', 'quote " inside'],
    ['3', 'multi\nline'],
  ]);
});

test('parseCsv handles a BOM, LF endings and tabs', () => {
  assert.deepEqual(parseCsv('\uFEFFa\tb\n1\t2\n', '\t'), [
    ['a', 'b'],
    ['1', '2'],
  ]);
});

test('jsonToCsv flattens nested objects into safe column names', () => {
  const { csv, rows, columns } = jsonToCsv({
    value: [
      { id: 1, 'first name': 'Ana', address: { city: 'Lima', geo: { lat: '1.5' } }, tags: ['a', 'b'] },
      { id: 2, 'first name': 'Bo', extra: true },
    ],
  });
  assert.equal(rows, 2);
  assert.deepEqual(columns, ['id', 'first_name', 'address_city', 'address_geo_lat', 'tags', 'extra']);
  const parsed = parseCsv(csv);
  assert.deepEqual(parsed[1], ['1', 'Ana', 'Lima', '1.5', '["a","b"]', '']);
  assert.deepEqual(parsed[2], ['2', 'Bo', '', '', '', 'true']);
});

test('jsonToCsv rejects empty input', () => {
  assert.throws(() => jsonToCsv([]), /no records/);
});

test('safeColumnName strips characters Delta does not allow', () => {
  assert.equal(safeColumnName(' Order Total ($) '), 'Order_Total');
  assert.equal(safeColumnName('***'), 'column');
});
