'use strict';
window.MathJax={
  loader:{load:['a11y/assistive-mml','ui/safe']},
  tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]'],['$$','$$']],processEnvironments:true,maxBuffer:10000,maxMacros:1000,require:{defaultAllow:false}},
  chtml:{fontURL:'/static/vendor/mathjax/es5/output/chtml/fonts/woff-v2'},
  options:{enableMenu:false,enableAssistiveMml:true,safeOptions:{allow:{URLs:'none',classes:'none',cssIDs:'none',styles:'none'}}}
};
