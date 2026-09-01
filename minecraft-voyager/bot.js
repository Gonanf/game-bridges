const mineflayer = (()=>{try{return require('./Voyager/voyager/env/mineflayer/node_modules/mineflayer')}catch{return require('mineflayer')}})()
const PROVIDER = process.env.PROVIDER_URL || 'http://127.0.0.1:8099/v1/chat/completions'
const MODEL = process.env.MODEL || 'jano'
const BRIDGE = 'http://127.0.0.1:8099/api/game/event'
const bot = mineflayer.createBot({host:'127.0.0.1', port:45123, username:'VoyagerKateto'})
let looping=false
async function post(text, voice='jane'){try{await fetch(BRIDGE,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({game:'minecraft',event_type:'game_event',voice_id:voice,text,rms:0.2,state:{}})})}catch(e){}}
async function think(){
  if(looping) return; looping=true
  try{
    const pos = bot.entity ? `${Math.floor(bot.entity.position.x)},${Math.floor(bot.entity.position.y)},${Math.floor(bot.entity.position.z)}` : 'unknown'
    const inv = bot.inventory ? bot.inventory.items().map(i=>i.name).join(',').slice(0,80) : ''
    const prompt = `[Minecraft GameMode voyager] Bot ${pos} inv:[${inv}] hp:${bot.health} food:${bot.food} vs ${bot.game ? '' : ''} Voyager skills: exploreUntil, mineBlock, craftItem, placeItem, killMob. Respond ONLY with one: forward 2s | jump | chat <msg> | dig | explore | craft`
    const r = await fetch(PROVIDER,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:MODEL,messages:[{role:'user',content:prompt}],temperature:0.7,max_tokens:30})})
    const j = await r.json()
    const txt = (j.choices?.[0]?.message?.content || j.choices?.[0]?.text || '').trim().toLowerCase()
    console.log('LLM:',txt)
    await post(`Voyager thinks: ${txt}`, 'doktor')
    if(txt.includes('forward')){ bot.setControlState('forward',true); setTimeout(()=>bot.setControlState('forward',false),2000)}
    else if(txt.includes('jump')) bot.setControlState('jump',true), setTimeout(()=>bot.setControlState('jump',false),500)
    else if(txt.startsWith('chat ')) bot.chat(txt.slice(5).slice(0,50))
    else if(txt.includes('dig')){ const b=bot.blockAt(bot.entity.position.offset(0,-1,0)); if(b) try{await bot.dig(b)}catch{}}
    else if(txt.includes('left')){ bot.setControlState('left',true); setTimeout(()=>bot.setControlState('left',false),800)}
    else if(txt.includes('right')){ bot.setControlState('right',true); setTimeout(()=>bot.setControlState('right',false),800)}
    else { bot.setControlState('forward',true); setTimeout(()=>bot.setControlState('forward',false),1200)}
  }catch(e){ console.log('think fail',e.message); bot.setControlState('forward',true); setTimeout(()=>bot.setControlState('forward',false),1000)}
  looping=false
}
bot.on('spawn', async()=>{
  console.log('spawned')
  const skills = (process.env.VOYAGER_SKILLS || process.env.MINECRAFT_SKILLS || 'exploreUntil,mineBlock,craftItem,placeItem,killMob,smeltItem').split(',').map(s=>s.trim()).filter(Boolean)
  await fetch(BRIDGE,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({game:'minecraft',event_type:'game_start',voice_id:'jane',text:'Minecraft GameMode voyager',rms:0.2,state:{profile:'minecraft',mode:'voyager',skills, voyager_skills:skills}})})
  await post('Voyager spawn MC 45123 via Kateto 8099 LLM', 'conquest')
  setInterval(think, 15000)
  setTimeout(think, 4000)
})
bot.on('chat',(u,m)=>{console.log(u+': '+m); post(`${u}: ${m}`, 'jane')})
bot.on('kicked', console.log)
bot.on('error', e=>console.log('error',e.message))
