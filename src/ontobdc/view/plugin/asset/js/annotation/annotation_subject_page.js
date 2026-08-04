(function (global) {
  "use strict";
  const lifecycle=global.OntoBDCAnnotationLifecycle;
  const values=value=>Array.isArray(value)?value:value==null?[]:[value];
  const center=selector=>{if(!selector)return null;if(Array.isArray(selector.points)&&selector.points.length){const p=selector.points[0];return{x:p.x,y:p.y};}if(Number.isFinite(selector.x))return{x:selector.x+selector.width/2,y:selector.y+selector.height/2};return null;};
  const intersects=(a,b)=>a&&b&&Number.isFinite(a.x)&&Number.isFinite(b.x)&&a.x<=b.x+b.width&&b.x<=a.x+a.width&&a.y<=b.y+b.height&&b.y<=a.y+a.height;
  const close=(a,b)=>{const ac=center(a),bc=center(b);return ac&&bc&&Math.hypot(ac.x-bc.x,ac.y-bc.y)<=0.12;};

  function spatialClusters(annotations) {
    const byRepresentation=new Map(),without=[];
    annotations.forEach(a=>{if(!a.selector){without.push(a);return;}const key=a.representationSource||a.logicalSource;if(!key){without.push(a);return;}if(!byRepresentation.has(key))byRepresentation.set(key,[]);byRepresentation.get(key).push(a);});
    const groups=[];
    byRepresentation.forEach((items,representation)=>{
      const pending=items.slice();
      while(pending.length){const cluster=[pending.shift()];for(let i=pending.length-1;i>=0;i--){if(cluster.some(a=>close(a.selector,pending[i].selector)||intersects(a.selector,pending[i].selector))){cluster.push(pending.splice(i,1)[0]);}}groups.push({representation,annotations:cluster});}
    });
    if(without.length)groups.push({representation:null,annotations:without});
    return groups;
  }

  function createPage(configuration){
    const options=Object.assign({annotations:[],subjects:[],subjectUri:null,labels:{},onOpen:function(){}},configuration||{});
    const hash=new URLSearchParams(location.hash.slice(1));let active=hash.get("tab")||"space",selectedAnnotation=hash.get("annotation");
    const root=document.createElement("article");root.className="ontobdc-subject-page";
    const subject=options.subjects.find(s=>s.uri===options.subjectUri)||{uri:options.subjectUri,label:options.labels.unassigned||"Unassigned subjects",description:""};
    const annotations=options.annotations.filter(a=>options.subjectUri?values(a.subjects).includes(options.subjectUri):!values(a.subjects).length);
    const people=new Set(),resources=new Set(),categories=new Set(),times=[];
    annotations.forEach(a=>{categories.add(a.type);[a.annotatedBy,a.modifiedBy,a.resolvedBy,(a.properties||{}).recordedBy].concat(values(a.assignedTo)).filter(Boolean).forEach(x=>people.add(x));[a.logicalSource,a.representationSource,(a.properties||{}).recordResource].filter(Boolean).forEach(x=>resources.add(x));[a.annotatedAt,a.created,a.modified,(a.properties||{}).recordedAt,(a.properties||{}).resolvedAt].filter(Boolean).forEach(x=>times.push(x));});
    const header=document.createElement("header"),title=document.createElement("h1"),description=document.createElement("p"),technical=document.createElement("code"),summary=document.createElement("p");
    title.textContent=subject.label||subject.uri;description.textContent=subject.description||"";technical.textContent=subject.uri||"";summary.textContent=annotations.length+" annotations · "+categories.size+" categories · "+people.size+" people · "+resources.size+" resources"+(times.length?" · "+times.sort()[0]+" — "+times.sort().at(-1):"");header.append(title,description,technical,summary);
    const hierarchy=document.createElement("p");hierarchy.textContent=[].concat(values(subject.broader).map(x=>"↑ "+x),values(subject.narrower).map(x=>"↓ "+x)).join(" · ");if(hierarchy.textContent)header.append(hierarchy);
    const tabs=document.createElement("nav");tabs.setAttribute("aria-label",options.labels.views||"Subject views");const panel=document.createElement("section");
    function tab(name){const b=document.createElement("button");b.type="button";b.textContent=options.labels[name]||name;b.onclick=()=>{active=name;render();};b.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();active=name;render();}};return b;}
    ["space","timeline","people"].forEach(n=>tabs.appendChild(tab(n)));root.append(header,tabs,panel);
    function item(a,label){const b=document.createElement("button");b.type="button";b.dataset.annotationId=a.id;b.setAttribute("aria-current",String(a.id===selectedAnnotation));b.textContent=label||a.body||a.id;b.onclick=()=>{selectedAnnotation=a.id;writeHash();options.onOpen(a);};return b;}
    function renderSpace(){spatialClusters(annotations).forEach((cluster,index)=>{const group=document.createElement("section"),h=document.createElement("h2");h.textContent=cluster.representation||(options.labels.withoutPosition||"Without spatial position");group.append(h);if(cluster.representation){const sub=document.createElement("p");sub.textContent=(options.labels.spatialGroup||"Spatial group")+" "+(index+1);group.append(sub);}cluster.annotations.forEach(a=>group.append(item(a)));panel.append(group);});}
    function renderTimeline(){const events=[];annotations.forEach(a=>(lifecycle?lifecycle.events(a):[]).forEach(event=>events.push({annotation:a,event})));events.sort((a,b)=>String(a.event.at).localeCompare(String(b.event.at)));events.forEach(x=>panel.append(item(x.annotation,x.event.at+" · "+(options.labels[x.event.type]||x.event.type)+" · "+(x.annotation.body||x.annotation.id))));}
    function renderPeople(){const map=new Map();annotations.forEach(a=>{const p=a.properties||{},pairs=[[a.annotatedBy,"author"],[a.modifiedBy,"modifier"],[a.resolvedBy,"resolver"],[p.recordedBy,"recorder"]].concat(values(a.assignedTo).map(x=>[x,"assignee"]));pairs.forEach(pair=>{if(!pair[0])return;if(!map.has(pair[0]))map.set(pair[0],[]);map.get(pair[0]).push({annotation:a,role:pair[1]});});});map.forEach((entries,person)=>{const group=document.createElement("section"),h=document.createElement("h2");h.textContent=person;group.append(h);entries.forEach(x=>group.append(item(x.annotation,(options.labels[x.role]||x.role)+" · "+(x.annotation.body||x.annotation.id))));panel.append(group);});}
    function writeHash(){const params=new URLSearchParams(location.hash.slice(1));params.set("subject",options.subjectUri||"");params.set("tab",active);if(selectedAnnotation)params.set("annotation",selectedAnnotation);history.replaceState(null,"","#"+params.toString());}
    function render(){Array.from(tabs.children).forEach((b,i)=>b.setAttribute("aria-pressed",String(["space","timeline","people"][i]===active)));panel.replaceChildren();if(active==="space")renderSpace();else if(active==="timeline")renderTimeline();else renderPeople();if(!panel.children.length){const p=document.createElement("p");p.textContent=options.labels.empty||"No annotations.";panel.append(p);}writeHash();}
    render();return Object.freeze({root,setActive:value=>{active=value;render();},getActive:()=>active,selectAnnotation:id=>{selectedAnnotation=id;render();},getSpatialClusters:()=>spatialClusters(annotations)});
  }
  global.OntoBDCSubjectPage=Object.freeze({create:createPage,spatialClusters:spatialClusters});
}(globalThis));
