// Palettes carry a default shell layout; each can also use any other layout.
const make = (id, name, note, colors, layout='classic', dark=true) => ({
  id, name, note, layout, dark,
  colors: Object.fromEntries(['bg','side','panel','editor','text','muted','line','accent','onAccent','selection'].map((k,i)=>[k,colors[i]]))
});
export const themes = [
  make('vscode','VS Code Dark','The familiar starting point',['#181818','#181818','#252526','#1f1f1f','#e4e4e4','#a3a3a3','#343434','#007acc','#ffffff','#264f78']),
  make('vscode-light','VS Code Light','Clear, familiar, full daylight',['#f3f3f3','#f6f6f6','#ffffff','#ffffff','#24292f','#5f6670','#d7dce2','#0069c2','#ffffff','#cfe8ff'],'classic',false),
  make('github-dark','GitHub Dark','Quiet graphite, precise edges',['#010409','#0d1117','#161b22','#0d1117','#e6edf3','#9da7b3','#30363d','#2f81f7','#ffffff','#19365d']),
  make('github-light','GitHub Light','White canvas, fine blue details',['#f6f8fa','#f6f8fa','#ffffff','#ffffff','#24292f','#57606a','#d0d7de','#0969da','#ffffff','#ddf4ff'],'classic',false),
  make('tokyo','Tokyo Night','Rounded panels, electric blue',['#151624','#1b1d30','#22253b','#1a1b2b','#d6ddff','#a2afd4','#343955','#82aaff','#18213b','#34436d'],'studio'),
  make('mocha','Catppuccin Mocha','Soft lavender, generous curves',['#181825','#1e1e2e','#262638','#1e1e2e','#cdd6f4','#a6adc8','#45475a','#cba6f7','#1e1e2e','#45405f'],'studio'),
  make('nord','Nord','Arctic blues with room to breathe',['#242b36','#2e3440','#343d4b','#2e3440','#eceff4','#b6c2d0','#4c566a','#88c0d0','#202c38','#46536a'],'studio'),
  make('dracula','Dracula','Bold violet, midnight surfaces',['#20212b','#282a36','#303342','#282a36','#f8f8f2','#b5b3c7','#45485d','#bd93f9','#242232','#48405e'],'studio'),
  make('rose','Rosé Pine','Warm ink and dusty rose',['#16141f','#1f1d2e','#29253a','#191724','#e0def4','#aaa5c3','#40394f','#ebbcba','#2b2134','#4b3d53'],'notebook'),
  make('gruvbox','Gruvbox','Warm charcoal, brass and grain',['#1d2021','#282828','#32302f','#282828','#ebdbb2','#bdae93','#504945','#fabd2f','#282828','#504832'],'notebook'),
  make('solarized','Solarized','Balanced teal, a restrained classic',['#002b36','#073642','#0b3c47','#002b36','#c7d7d8','#9cbbbd','#285563','#b9a128','#052f38','#244d57']),
  make('monokai','Monokai','Inky black and sharp lime',['#1e1f1c','#272822','#30312a','#272822','#f8f8f2','#b7b8a6','#484b3e','#a6e22e','#252b16','#414a2c']),
  make('aurora','Aurora','Floating jade panels, a softer glow',['#0c1b1b','#122727','#193333','#102523','#d7f1e8','#9bbdb3','#2b4b45','#6ee7b7','#103a2b','#264e43'],'studio'),
  make('midnight','Midnight Signal','High contrast, icy blue light',['#080d19','#0c1424','#111f34','#0b1425','#e1edff','#a1b6d4','#263a58','#69d6ff','#0a2838','#1d3e58'],'neon'),
  make('ocean','Deep Ocean','Tidal blue with rounded cards',['#091b29','#102737','#173244','#102333','#d7edf4','#9dbacb','#2d4b60','#61d1da','#0a3034','#25515c'],'studio'),
  make('matcha','Matcha','Soft sage, airy rounded surfaces',['#e9eee6','#eff3eb','#fafcf7','#fafcf7','#263b2b','#5e715d','#cbd7c6','#43734c','#ffffff','#d7e8cf'],'studio',false),
  make('paper','Paper & Ink','Editorial type and a warm white page',['#edeae3','#f2efe8','#fffdf8','#fffdf8','#342f27','#746c5e','#d8d0c2','#8c5932','#ffffff','#ead9bf'],'notebook',false),
  make('latte','Catppuccin Latte','Cream, lilac and soft edges',['#e6e9ef','#eff1f5','#ffffff','#fafbfe','#4c4f69','#646781','#c6cbd7','#7958bd','#ffffff','#e3d9f5'],'studio',false),
  make('candy','Pastel Studio','Playful peach and lilac cards',['#f0eaf3','#f8f0f6','#fffbff','#fffbff','#46334d','#78627f','#ded0e3','#9a4b82','#ffffff','#f0d6ec'],'studio',false),
  make('terminal','Terminal Green','Compact, square, all monospace',['#080d09','#0d140e','#111b12','#090f0a','#c5eccb','#88af8c','#29412b','#a2e89f','#0b230f','#26492b'],'terminal'),
];

export const layouts = [
  {id:'classic',name:'Classic',note:'Familiar tabs and joined panes'},
  {id:'studio',name:'Rounded studio',note:'Floating cards and generous curves'},
  {id:'notebook',name:'Editorial',note:'Warm headings and a page-like canvas'},
  {id:'neon',name:'Signal',note:'Fine accent lines and focused surfaces'},
  {id:'terminal',name:'Compact terminal',note:'Square corners and monospace controls'}
];
