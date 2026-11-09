// Locate statements with MySQL string/comment rules. Compound routines with
// custom delimiters run as a whole script so a semicolon never splits a body.
export function statements(text) {
  if (/^\s*DELIMITER\s|\bCREATE\s+(?:DEFINER\s*=\s*\S+\s+)?(?:PROCEDURE|FUNCTION|TRIGGER|EVENT)\b/im.test(text))
    return [{from:0,to:text.length,text}];
  const result=[]; let start=0, quote=null, comment=null;
  for(let i=0;i<text.length;i++) {
    const c=text[i], n=text[i+1];
    if(comment==='line'){if(c==='\n')comment=null;continue;}
    if(comment==='block'){if(c==='*'&&n==='/'){comment=null;i++;}continue;}
    if(quote){
      if(c==='\\'){i++;continue;}
      if(c===quote){if(n===quote){i++;}else quote=null;}
      continue;
    }
    if(c==="'"||c==='"'||c==='`'){quote=c;continue;}
    if(c==='#'||(c==='-'&&n==='-'&&(!text[i+2]||/\s/.test(text[i+2])))){comment='line';continue;}
    if(c==='/'&&n==='*'){comment='block';i++;continue;}
    if(c===';'){result.push({from:start,to:i+1,text:text.slice(start,i+1)});start=i+1;}
  }
  if(start<text.length)result.push({from:start,to:text.length,text:text.slice(start)});
  return result.filter(s=>s.text.replace(/\/\*[\s\S]*?\*\/|--(?=\s|$)[^\n]*|#[^\n]*/g,'').replace(/;/g,'').trim());
}
export function currentStatement(text, cursor) {
  const parts=statements(text);
  return parts.find(s=>cursor>=s.from&&cursor<s.to)||parts.find(s=>s.to>=cursor)||parts.at(-1)||{from:0,to:text.length,text};
}
