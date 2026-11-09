import test from 'node:test';
import assert from 'node:assert/strict';
import {statements, currentStatement} from '../desk/src/sql.js';

test('semicolons inside strings, escaped quotes and identifiers stay inside their statement',()=>{
  const query="SELECT 'one; two', 'it\\'s; fine', `a;b`; SELECT \"x; y\";";
  assert.equal(statements(query).length,2);
  assert.equal(currentStatement(query,query.length).text.trim(),'SELECT "x; y";');
});
test('MySQL line and block comments do not create phantom statements',()=>{
  const query='-- first; comment\nSELECT 1;\n# second; comment\n/* a ; block */ SELECT 2;\n-- just a trailing comment';
  assert.equal(statements(query).length,2);
  assert.match(currentStatement(query,query.indexOf('SELECT 2')).text,/SELECT 2;/);
});
test('a compound routine runs as a single script, preserving its delimiter',()=>{
  const query='DELIMITER $$\nCREATE PROCEDURE example() BEGIN SELECT 1; SELECT 2; END$$\nDELIMITER ;\nCALL example();';
  assert.equal(statements(query).length,1);
  assert.equal(currentStatement(query,query.indexOf('SELECT 2')).text,query);
});
test('minus-minus without whitespace is an expression, not a MySQL comment',()=>{
  assert.equal(statements('SELECT 5--2; SELECT 3;').length,2);
});
test('the current statement follows the cursor and trailing empty space is harmless',()=>{
  const query='SELECT 1;\n\nSELECT 2;\n';
  assert.equal(currentStatement(query,3).text,'SELECT 1;');
  assert.match(currentStatement(query,query.length).text,/SELECT 2;/);
});
