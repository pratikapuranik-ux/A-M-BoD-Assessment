/* Application state (in memory). The period defaults to the current calendar quarter until a company is opened. */
const S={page:'landing',stage:1,sub:'setup',tab:'report',name:'',email:'',
 mode:'director_request',period:(d=>d.getFullYear()+'-Q'+(Math.floor(d.getMonth()/3)+1))(new Date()),priorSel:[],listed:false,qFiles:[],other:[],docs:{},answers:{},ratings:{},
 oiDone:false,ioDone:false,final:false,saved:false,srcf:'all',rdim:[],srcq:'',history:[],
 company:null,add:null,drawer:null,dashStage:'oi',job:null};
for(let i=1;i<=D.docs.length;i++) S.docs[i]={on:false,files:[]};
for(let i=1;i<=D.q.length;i++) S.answers[i]='';
