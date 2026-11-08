/* AEROCOST AI 2.0 — transparent, illustrative engineering quotation engine.
   Entirely local: no external services, proprietary CAD parsing or hidden ML claims. */
(() => {
'use strict';
const FAMILIES = {
 'Propeller_Hub':{shape:'hub',factor:.61,stock:2.1,holes:8,complexity:.73},
 'Blade_Root_Fitting':{shape:'bracket',factor:.54,stock:2.45,holes:12,complexity:.75},
 'Transmission_Shaft':{shape:'shaft',factor:.57,stock:1.7,holes:4,complexity:.54},
 'Gearbox_Housing':{shape:'housing',factor:.43,stock:2.4,holes:16,complexity:.8},
 'Actuator_Housing':{shape:'housing',factor:.48,stock:2.15,holes:10,complexity:.7},
 'Structural_Bracket':{shape:'bracket',factor:.35,stock:2.55,holes:8,complexity:.62},
 'Bearing_Carrier':{shape:'hub',factor:.55,stock:2.08,holes:8,complexity:.63},
 'Flange':{shape:'hub',factor:.59,stock:1.78,holes:6,complexity:.49},
 'Hydraulic_Block':{shape:'housing',factor:.70,stock:1.65,holes:18,complexity:.75},
 'Mounting_Clevis':{shape:'bracket',factor:.46,stock:2.25,holes:6,complexity:.61},
};
const MATERIALS = {
 'Al_7075_T6':{density:2.81,price:18,index:1.12,label:'Aluminum 7075-T6'},
 'Al_7050_T7451':{density:2.83,price:25,index:1.04,label:'Aluminum 7050-T7451'},
 'Al_6061_T6':{density:2.70,price:12,index:1.28,label:'Aluminum 6061-T6'},
 'Ti_6Al_4V':{density:4.43,price:75,index:.27,label:'Titanium Ti-6Al-4V'},
 'Steel_4340':{density:7.85,price:10,index:.60,label:'Steel 4340'},
 'Steel_17_4PH':{density:7.75,price:25,index:.45,label:'Stainless steel 17-4PH'},
 'Inconel_718':{density:8.19,price:110,index:.19,label:'Inconel 718'},
 'SS_316L':{density:7.99,price:22,index:.49,label:'Stainless steel 316L'},
 'Bronze_C954':{density:7.45,price:29,index:.75,label:'Aluminium bronze C954'}
};
const ROUTES = [
 {id:'economy',name:'3-axis / Economy',machine:'CNC_3axis',rate:75,power:8,mrr:40,setup:135,cam:115,finish:1.12,handling:1.32,description:'Accessible machine rate; more setups and limited complex-surface access.'},
 {id:'precision',name:'5-axis / Precision',machine:'CNC_5axis',rate:130,power:15,mrr:34,setup:85,cam:145,finish:.80,handling:.80,description:'Fewer reorientations, improved access; higher hourly machine cost.'},
 {id:'volume',name:'HMC / Production',machine:'HMC',rate:118,power:16,mrr:48,setup:235,cam:135,finish:.98,handling:.75,description:'Fast material removal and repeat production; higher preparation investment.'}
];
const BOUNDS={length:[30,550],width:[22,300],height:[8,220],batch:[1,500],tolerance:[.008,.3],roughness:[.4,6.3],complexity:[.1,1],holes:[0,40],materialPrice:[.65,1.5],productivity:[.7,1.3]};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const norm=x=>Number(x)||0;
const round=(x,n=2)=>Number(x.toFixed(n));
function sanitize(p={}){
 let fam=FAMILIES[p.family]?p.family:'Propeller_Hub';
 let f=FAMILIES[fam];
 let mat=MATERIALS[p.material]?p.material:'Al_7075_T6';
 const c={family:fam,material:mat,length:clamp(norm(p.length)||210,30,550),width:clamp(norm(p.width)||118,22,300),height:clamp(norm(p.height)||54,8,220),batch:clamp(Math.round(norm(p.batch)||24),1,500),tolerance:clamp(norm(p.tolerance)||.04,.008,.3),roughness:clamp(norm(p.roughness)||1.6,.4,6.3),complexity:clamp(norm(p.complexity)||f.complexity,.1,1),holes:clamp(Math.round(p.holes===0?0:(norm(p.holes)||f.holes)),0,40),inspection:['standard','enhanced','critical'].includes(p.inspection)?p.inspection:'enhanced', materialPrice:clamp(norm(p.materialPrice)||1,.65,1.5),productivity:clamp(norm(p.productivity)||1,.7,1.3)};
 return c;
}
function geometry(c){
 let fam=FAMILIES[c.family],box=c.length*c.width*c.height/1000; // mm³ → cm³
 let shapeFactor=fam.factor*(1-.12*(c.complexity-.5));
 let net=box*shapeFactor;
 let buyToFly=fam.stock*(.85+.38*c.complexity);
 let stock=net*buyToFly;
 let area=2*(c.length*c.width+c.length*c.height+c.width*c.height)*(.75+.24*c.complexity);
 let mass=net*MATERIALS[c.material].density/1000;
 let stockMass=stock*MATERIALS[c.material].density/1000;
 return {net,stock,removed:stock-net,buyToFly,area,mass,stockMass,stockDimensions:[c.length,c.width,c.height],stockMassDescription:'Stock mass is modeled from a family-specific buy-to-fly factor; it is not extracted from a CAD model.'};
}
function estimateRoute(c, route){
 const m=MATERIALS[c.material],g=geometry(c);
 let precision=Math.max(0,Math.log10(.08/c.tolerance));
 let quality=['standard','enhanced','critical'].indexOf(c.inspection);
 const feasible=!(route.id==='economy'&&(c.complexity>.80||c.tolerance<.018||c.roughness<.65));
 let warnings=[];
 if(!feasible)warnings.push('3-axis route screened out: tight tolerance, surface finish, or access complexity. Engineering review required.');
 if(c.material==='Inconel_718')warnings.push('Nickel alloy machining assumptions require tool-life trials and conservative cutting data.');
 if(c.tolerance<.018)warnings.push('Sub-0.018 mm tolerance needs a dedicated capability study and inspection strategy.');
 let effectiveMRR=route.mrr*m.index*c.productivity*(1-.29*c.complexity); // cm³/min illustrative
 let roughMin=g.removed/effectiveMRR;
 let finishingAreaRate=1650*m.index*c.productivity/(1+.75*precision);
 let finishMin=g.area/Math.max(150,finishingAreaRate)*route.finish*(.85+.5*c.complexity);
 let drillingMin=c.holes*(.85+.012*c.height/Math.max(.23,m.index))*route.handling;
 let runMin=(roughMin+finishMin+drillingMin)*1.05;
 let setupMin=route.setup*(1+.62*c.complexity+precision*.26);
 let camMin=route.cam*(.55+c.complexity*.95)*(1+.025*c.holes);
 let material=g.stockMass*m.price*c.materialPrice*1.10;
 let machine=runMin/60*route.rate;
 let setup=setupMin/60*route.rate/c.batch;
 let programming=camMin/60*82/c.batch;
 let tooling=(runMin/60)*(6.8+22/Math.max(.2,m.index))*(.86+.29*c.productivity*c.productivity);
 let electrical=runMin/60*route.power*.19;
 let inspectionHours=.18+.016*c.holes+precision*.52+quality*.43+c.complexity*.25;
 let inspection=inspectionHours*58;
 let expectedRework=(machine+inspection)*(.015+c.complexity*.025+quality*.015);
 let traceability=[14,36,82][quality];
 let components={
   'Raw material & stock':material,
   'CNC machining':machine,
   'Batch setup allocation':setup,
   'CAM programming allocation':programming,
   'Cutting tools':tooling,
   'Machine electricity':electrical,
   'Inspection & traceability':inspection+traceability,
   'Expected rework':expectedRework,
 };
 let direct=Object.values(components).reduce((a,b)=>a+b,0);
 let scrapRate=clamp(.016+.052*c.complexity+.009*precision+quality*.006,.02,.16);
 let scrapAllowance=direct/(1-scrapRate)-direct;
 let overhead=(direct+scrapAllowance)*.085;
 components['Scrap allowance']=scrapAllowance;
 components['Indirect overhead']=overhead;
 let unit=direct+scrapAllowance+overhead;
 let total=unit*c.batch;
 let leadHours=setupMin/60+camMin/60+runMin*c.batch/60+(inspectionHours*c.batch)*.55;
 let machiningCostPerPart=machine+setup+programming+tooling+electrical;
 let operations=[
  {name:'Raw stock procurement',time:0,cost:material,machine:'Material planning',detail:`${g.stockMass.toFixed(2)} kg at €${(m.price*c.materialPrice).toFixed(2)}/kg + stock allowance`},
  {name:'CAM programming',time:camMin/c.batch,cost:programming,machine:'CAM / Engineering',detail:'Program time amortized across batch; assumed €82/h'},
  {name:'Setup & workholding',time:setupMin/c.batch,cost:setup,machine:route.machine,detail:'Machine setup amortized across batch'},
  {name:'Rough machining',time:roughMin,cost:machine*roughMin/(roughMin+finishMin+drillingMin),machine:route.machine,detail:`Effective MRR ${effectiveMRR.toFixed(1)} cm³/min`},
  {name:'Finish machining',time:finishMin,cost:machine*finishMin/(roughMin+finishMin+drillingMin),machine:route.machine,detail:`Tolerance ${c.tolerance} mm · Ra ${c.roughness} µm`},
  {name:'Drilling / hole features',time:drillingMin,cost:machine*drillingMin/(roughMin+finishMin+drillingMin),machine:route.machine,detail:`${c.holes} nominal hole features`},
  {name:'Inspection & traceability',time:inspectionHours*60,cost:inspection+traceability,machine:'Quality / CMM',detail:`${c.inspection} verification scenario`},
 ];
 return {id:route.id,name:route.name,machine:route.machine,description:route.description,feasible,warnings,unit:round(unit),total:round(total),components:Object.entries(components).map(([name,cost])=>({name,value:round(cost)})),operations:operations.map(o=>({...o,time:round(o.time,1),cost:round(o.cost)})),timeMinutes:round(runMin,1),leadHours:round(leadHours,1),setupMinutes:round(setupMin,1),camMinutes:round(camMin,1),mrr:round(effectiveMRR,1),scrapPercent:round(scrapRate*100,1),power:route.power,electricityKWh:round(runMin/60*route.power,2),emissionsKgIllustrative:round(runMin/60*route.power*.052,2),machiningCostPerPart:round(machiningCostPerPart)};
}
function evaluate(p){let c=sanitize(p),g=geometry(c);let routes=ROUTES.map(r=>estimateRoute(c,r));let feasible=routes.filter(r=>r.feasible);let best=feasible.reduce((a,b)=>a.unit<b.unit?a:b);let selected=routes.find(x=>x.id===p.route)||best;
 let lower=evaluateSensitivity(c,selected.id,'low'),upper=evaluateSensitivity(c,selected.id,'high');
 return {inputs:c,geometry:Object.fromEntries(Object.entries(g).map(([k,v])=>[k,typeof v==='number'?round(v,3):v])),routes,selected,minimum:best,sensitivity:{low:round(lower),high:round(upper),label:'Illustrative input-stress envelope, not a statistical confidence interval'},method:'Independent engineering scenario model. Not a prediction from the trained AEROCOST residual ML model.',assumptions:['Simplified parametric envelope, not CAD-extracted topology','Family-specific buy-to-fly ratios and material catalog prices are invented research inputs','Machining volume, MRR, feed, inspection and tooling approximations require shop-floor validation','Quality and emissions figures are illustrative and not certified industrial values']};
}
function evaluateSensitivity(c,id,side){let p={...c}; p.materialPrice=side==='low'?.90:1.10;p.productivity=side==='low'?1.13:.87;let out=estimateRoute(p,ROUTES.find(x=>x.id===id));return out.unit;}
window.AERO_ENGINE_V2={FAMILIES,MATERIALS,ROUTES,BOUNDS,sanitize,geometry,estimateRoute,evaluate};
})();
