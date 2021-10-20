import simplebot
from simplebot.bot import DeltaBot, Replies
from deltachat import Chat, Contact, Message
import sys
import os
from telethon.sessions import StringSession
from telethon import TelegramClient as TC
from telethon import functions
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, SendMessageRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.tl.types import InputPeerEmpty
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon import utils, errors
from telethon.errors import SessionPasswordNeededError
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import re
import time
import json
from datetime import datetime

version = "0.1.3"
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
login_hash = os.getenv('LOGIN_HASH')

global phonedb
phonedb = {}

global smsdb
smsdb = {}

global hashdb
hashdb = {}

global clientdb
clientdb = {}

global logindb
logindb = {}

global chatdb
chatdb = {}

loop = asyncio.new_event_loop()

@simplebot.hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.account.set_avatar('telegram.jpeg')
    bot.commands.register(name = "/eval" ,func = eval_func, admin = True)
    bot.commands.register(name = "/start" ,func = start_updater, admin = True)
    bot.commands.register(name = "/more" ,func = async_load_chat_messages)
    bot.commands.register(name = "/load" ,func = async_updater)
    bot.commands.register(name = "/exec" ,func = async_run, admin = True)
    bot.commands.register(name = "/login" ,func = async_login_num)
    bot.commands.register(name = "/sms" ,func = async_login_code)
    bot.commands.register(name = "/pass" ,func = async_login_2fa)
    bot.commands.register(name = "/token" ,func = async_login_session)
    bot.commands.register(name = "/logout" ,func = logout_tg)
    bot.commands.register(name = "/remove" ,func = remove_chat)
    bot.commands.register(name = "/down" ,func = async_down_media)
    bot.commands.register(name = "/c" ,func = async_click_button)
    bot.commands.register(name = "/b" ,func = async_send_cmd)
    bot.commands.register(name = "/search" ,func = async_search_chats)
    bot.commands.register(name = "/join" ,func = async_join_chats)
    bot.commands.register(name = "/preview" ,func = async_preview_chats)

async def save_delta_chats(replies, message):
    """This is for save the chats deltachat/telegram in Telegram Saved message user"""
    try:
       client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
       tf = open(message.get_sender_contact().addr+'.json', 'w')
       json.dump(chatdb[message.get_sender_contact().addr], tf)
       tf.close()
       await client.connect()
       my_id = await client(functions.users.GetFullUserRequest('me'))
       if my_id.pinned_msg_id:
          my_pin = await client.get_messages('me', ids=my_id.pinned_msg_id)                                      
          await client.edit_message('me',my_pin,'!!!Atención, este mensaje es parte del puente con deltachat, NO lo borre ni lo quite de los anclados o perdera el vinculo con telegram\n'+str(datetime.now()), file = message.get_sender_contact().addr+'.json')
       else:
          my_new_pin = await client.send_file('me', message.get_sender_contact().addr+'.json') 
          await client.pin_message('me', my_new_pin)
       await client.disconnect()
    except:
       code = str(sys.exc_info())
       print(code)
       if replies:
          replies.add(text=code)

def async_save_delta_chats(replies, message):
    loop.run_until_complete(save_delta_chats(replies, message))

async def load_delta_chats(message, replies):
    """This is for load the chats deltachat/telegram from Telegram saved message user"""
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para cargar sus chats!')
       return
    try:
       client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
       await client.connect()
       await client.get_dialogs()
       my_id = await client(functions.users.GetFullUserRequest('me'))
       my_pin = await client.get_messages('me', ids=my_id.pinned_msg_id)
       await client.download_media(my_pin)
       if os.path.isfile(message.get_sender_contact().addr+'.json'):
          tf = open(message.get_sender_contact().addr+'.json','r')
          chatdb[message.get_sender_contact().addr]=json.load(tf)
          tf.close()
       await client.disconnect()
    except:
       print('Error loading delta chats')

def async_load_delta_chats(message, replies):
    loop.run_until_complete(load_delta_chats(message, replies))
    
def remove_chat(payload, replies, message):
    """Remove current chat from telegram bridge. Example: /remove
       you can pass the all parametre to remove all chats like: /remove all"""
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para eliminar chats!')
       return
    if payload == 'all':
       chatdb[message.get_sender_contact().addr].clear()
       replies.add(text = 'Se desvincularon todos sus chats de telegram.')
    if str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():   
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
              del chatdb[message.get_sender_contact().addr][key]
              replies.add(text = 'Se desvinculó el chat delta '+str(message.chat.id)+' con el chat telegram '+key)
              break  
    else:
       replies.add(text = 'Este chat no está vinculado a telegram')
       return
    async_save_delta_chats(replies, message)
            
        
def logout_tg(payload, replies, message):
    """Logout from Telegram and delete the token session for the bot"""
    if message.get_sender_contact().addr in logindb:
       del logindb[message.get_sender_contact().addr]
       replies.add(text = 'Se ha cerrado la sesión en telegram, puede usar su token para iniciar en cualquier momento pero a nosotros se nos ha olvidado')
    else:
       replies.add(text = 'Actualmente no está logueado en el puente')
                                   
async def login_num(payload, replies, message):
    try:
       clientdb[message.get_sender_contact().addr] = TC(StringSession(), api_id, api_hash)
       await clientdb[message.get_sender_contact().addr].connect()
       me = await clientdb[message.get_sender_contact().addr].send_code_request(payload)
       hashdb[message.get_sender_contact().addr] = me.phone_code_hash
       phonedb[message.get_sender_contact().addr] = payload
       replies.add(text = 'Se ha enviado un codigo de confirmacion al numero '+payload+', por favor introdusca /sms CODIGO para iniciar')
    except:
       code = str(sys.exc_info())
       print(code)
       if replies:
          replies.add(text=code)

def async_login_num(payload, replies, message):
    """Start session in Telegram. Example: /login +5312345678"""
    loop.run_until_complete(login_num(payload, replies, message))
            
async def login_code(payload, replies, message):   
    try:
       if message.get_sender_contact().addr in phonedb and message.get_sender_contact().addr in hashdb and message.get_sender_contact().addr in clientdb:
          try:
              me = await clientdb[message.get_sender_contact().addr].sign_in(phone=phonedb[message.get_sender_contact().addr], phone_code_hash=hashdb[message.get_sender_contact().addr], code=payload)               
              logindb[message.get_sender_contact().addr]=clientdb[message.get_sender_contact().addr].session.save()
              replies.add(text = 'Se ha iniciado sesiòn correctamente, su token es:\n\n'+logindb[message.get_sender_contact().addr]+'\n\nUse /token mas este token para iniciar rápidamente.\n⚠No debe compartir su token con nadie porque pueden usar su cuenta con este.\n\nAhora puede escribir /load para cargar sus chats.')         
              await clientdb[message.get_sender_contact().addr].disconnect()
              del clientdb[message.get_sender_contact().addr]             
          except SessionPasswordNeededError:
              smsdb[message.get_sender_contact().addr]=payload
              replies.add(text = 'Tiene habilitada la autentificacion de doble factor, por favor introdusca /pass PASSWORD para completar el loguin.')
       else:
          replies.add(text = 'Debe introducir primero si numero de movil con /login NUMERO')
    except Exception as e:
       code = str(sys.exc_info())
       print(code)
       if replies:
          replies.add(text=code)

def async_login_code(payload, replies, message):
    """Confirm session in Telegram. Example: /sms 12345"""
    loop.run_until_complete(login_code(payload, replies, message))
    if message.get_sender_contact().addr in logindb:
       async_load_delta_chats(message = message, replies = replies)
            
async def login_2fa(payload, replies, message):   
    try:
       if message.get_sender_contact().addr in phonedb and message.get_sender_contact().addr in hashdb and message.get_sender_contact().addr in clientdb and message.get_sender_contact().addr in smsdb:
          me = await clientdb[message.get_sender_contact().addr].sign_in(phone=phonedb[message.get_sender_contact().addr], password=payload)               
          logindb[message.get_sender_contact().addr]=clientdb[message.get_sender_contact().addr].session.save()
          replies.add(text = 'Se ha iniciado sesiòn correctamente, su token es:\n\n'+logindb[message.get_sender_contact().addr]+'\n\nUse /token mas este token para iniciar rápidamente.\n⚠No debe compartir su token con nadie porque pueden usar su cuenta con este.\n\nAhora puede escribir /load para cargar sus chats')         
          await clientdb[message.get_sender_contact().addr].disconnect()
          del clientdb[message.get_sender_contact().addr]
          del smsdb[message.get_sender_contact().addr]            
       else:
          if message.get_sender_contact().addr not in clientdb:
             replies.add(text = 'Debe introducir primero si numero de movil con /login NUMERO')
          else:
             if message.get_sender_contact().addr not in smsdb:
                replies.add(text = 'Debe introducir primero el sms que le ha sido enviado con /sms CODIGO')    
    except:
       code = str(sys.exc_info())
       print(code)
       if replies:
          replies.add(text=code)

def async_login_2fa(payload, replies, message):
    """Confirm session in Telegram with 2FA. Example: /pass PASSWORD"""
    loop.run_until_complete(login_2fa(payload, replies, message))
    if message.get_sender_contact().addr in logindb:
       async_load_delta_chats(message = message, replies = replies)        
            
async def login_session(payload, replies, message):
    if message.get_sender_contact().addr not in logindb:
       try:
           client = TC(StringSession(payload), api_id, api_hash)
           await client.connect()
           my = await client.get_me()
           nombre = str(my.first_name)
           await client.disconnect() 
           replies.add(text='Ah iniciado sesión correctamente '+str(nombre))
           logindb[message.get_sender_contact().addr] = payload                      
       except:
          code = str(sys.exc_info())
          print(code)
          replies.add(text='Error al iniciar sessión:\n'+code)
    else:
       replies.add(text='Su token es:\n\n'+logindb[message.get_sender_contact().addr]) 

def async_login_session(payload, replies, message):
    """Start session using your token or show it if already login. Example: /token abigtexthashloginusingintelethonlibrary..."""
    loop.run_until_complete(login_session(payload, replies, message))
    if message.get_sender_contact().addr in logindb:
       async_load_delta_chats(message = message, replies = replies)

async def updater(bot, payload, replies, message):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para cargar sus chats!')
       return
    if message.get_sender_contact().addr not in chatdb:
       chatdb[message.get_sender_contact().addr] = {}     
    try:      
       if not os.path.exists(message.get_sender_contact().addr):
          os.mkdir(message.get_sender_contact().addr)
       contacto = message.get_sender_contact()
       client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
       await client.connect()
       me = await client.get_me()
       my_id = me.id
       all_chats = await client.get_dialogs()
       chats_limit = 5
       filtro = payload.replace(' ','_')
       replies.add(text = 'Obteniedo chats...'+filtro)
       for d in all_chats:
           if hasattr(d.entity,'username'):
              uname = str(d.entity.username)
           else:
              uname = 'None'
           ttitle = "Unknown"
           if hasattr(d,'title'):
              ttitle = d.title
           tid = str(d.id)
           find_only = False
           if payload.lower()=='#privates':
              private_only = hasattr(d.entity,'participants_count')
           else:
              private_only = False
           if payload!='' and payload.lower()!='#privates':
              if ttitle.lower().find(payload.lower())>=0 or tid is payload or uname is filtro:
                 find_only = False
              else:
                 find_only = True          
           if str(d.id) not in chatdb[message.get_sender_contact().addr] and not private_only and not find_only:             
              titulo = str(ttitle)+' ['+str(d.id)+']' 
              if my_id == d.id:
                 titulo = 'Mensajes guardados ['+str(d.id)+']'
              chat_id = bot.create_group(titulo, [contacto])
              img = await client.download_profile_photo(d.entity, message.get_sender_contact().addr)
              try:
                 if img and os.path.exists(img): 
                    chat_id.set_profile_image(img)
              except:
                 print('Error al poner foto del perfil al chat:\n'+str(img))
              chats_limit-=1
              chatdb[message.get_sender_contact().addr][str(d.id)] = str(chat_id.get_name())
              if d.unread_count == 0:
                 replies.add(text = "Estas al día con "+ttitle+" id:[`"+str(d.id)+"`]\n/more", chat = chat_id)
              else:
                 replies.add(text = "Tienes "+str(d.unread_count)+" mensajes sin leer de "+ttitle+" id:[`"+str(d.id)+"`]\n/more", chat = chat_id)
              if chats_limit<=0:
                 break
       await client.disconnect()          
       replies.add(text='Se agregaron '+str(5-chats_limit)+' chats a la lista!')
    except:
       code = str(sys.exc_info())
       replies.add(text=code)

def async_updater(bot, payload, replies, message):
    """Load chats from telegram. Example: /load
    you can pass #privates for load private only chats like: /load #privates
    or only chats with some words in title like: /load delta chat
    if you use the chat id only load this chat"""
    loop.run_until_complete(updater(bot, payload, replies, message))
    if message.get_sender_contact().addr in logindb:
       async_save_delta_chats(replies = replies, message = message)
        
async def down_media(message, replies, payload):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para descargar medios!')
       return
    if message.get_sender_contact().addr in chatdb and str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():
       if not os.path.exists(message.get_sender_contact().addr):
          os.mkdir(message.get_sender_contact().addr) 
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
               try:
                  client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
                  await client.connect()
                  await client.get_dialogs()
                  if key.lstrip('-').isnumeric():
                     target = int(key)
                  else:
                     target = key
                  tchat = await client(functions.messages.GetPeerDialogsRequest(peers=[target] ))
                  ttitle = 'Unknown'
                  if hasattr(tchat,'chats') and tchat.chats:
                     ttitle = tchat.chats[0].title
                  all_messages = await client.get_messages(target, ids = [int(payload)])
                  for m in all_messages:
                      if True:
                         mquote = ''
                         file_attach = 'archivo'
                        
                         #check if message is a reply
                         if hasattr(m,'reply_to'):
                            if hasattr(m.reply_to,'reply_to_msg_id'):
                               mensaje = await client.get_messages(target, ids = [m.reply_to.reply_to_msg_id])
                               if mensaje:
                                  mquote = '"'+str(mensaje[0].text)+'"\n'
                                
                         #extract sender name       
                         if hasattr(m.sender,'first_name') and m.sender.first_name:
                            send_by = str(m.sender.first_name)+":\n"
                         else:
                            send_by = ""
                          
                         #check if message have document
                         if hasattr(m,'document') and m.document:
                            if m.document.size<20971520:
                               file_attach = await client.download_media(m.document, message.get_sender_contact().addr)
                               replies.add(text = send_by+file_attach+"\n"+str(m.message), filename = file_attach)
                            else:
                               if hasattr(m.document,'attributes') and m.document.attributes:
                                  if hasattr(m.document.attributes[0],'file_name'):
                                     file_attach = m.document.attributes[0].file_name
                                  if hasattr(m.document.attributes[0],'title'):
                                     file_attach = m.document.attributes[0].title
                               replies.add(text = send_by+str(m.message)+"\n"+file_attach+" "+str(sizeof_fmt(m.document.size))+"\n/down_"+str(m.id))
                            
                         #check if message have a photo   
                         if hasattr(m,'media') and m.media:
                            if hasattr(m.media,'photo'):
                               if m.media.photo.sizes[1].size<20971520:
                                  file_attach = await client.download_media(m.media, message.get_sender_contact().addr)
                                  replies.add(text = send_by+file_attach+"\n"+str(m.message), filename = file_attach)
                               else:
                                  replies.add(text = send_by+str(m.message)+"\nFoto de "+str(sizeof_fmt(m.media.photo.sizes[1].size))+"/down_"+str(m.id))
                         print('Descargando mensaje '+str(m.id))
                      else:
                         break
                  await client.disconnect()
               except:
                  code = str(sys.exc_info())
                  replies.add(text=code)
               break
    else:
       replies.add(text='Este no es un chat de telegram')

def async_down_media(message, replies, payload):
    """Download media message from telegram in a chat"""
    loop.run_until_complete(down_media(message, replies, payload))
    
async def click_button(message, replies, payload):
    parametros = payload.split()
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para descargar medios!')
       return
    if message.get_sender_contact().addr in chatdb and str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
               try:
                  client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
                  await client.connect()
                  await client.get_dialogs()
                  if key.lstrip('-').isnumeric():
                     target = int(key)
                  else:
                     target = key
                  tchat = await client(functions.messages.GetPeerDialogsRequest(peers=[target] ))
                  all_messages = await client.get_messages(target, ids = [int(parametros[0])])
                  for m in all_messages:
                      await m.click(int(parametros[1]),int(parametros[2]))                
                  await client.disconnect()
               except:
                  code = str(sys.exc_info())
                  replies.add(text=code)
               break
    else:
       replies.add(text='Este no es un chat de telegram')
    
def async_click_button(message, replies, payload):
    """Make click on a message bot button"""
    loop.run_until_complete(click_button(message, replies, payload))
    parametros = payload.split()
    loop.run_until_complete(load_chat_messages(message=message, replies=replies, payload=parametros[0]))

async def load_chat_messages(message, replies, payload):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para cargar los mensajes!')
       return
    if message.get_sender_contact().addr in chatdb and str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():
       if not os.path.exists(message.get_sender_contact().addr):
          os.mkdir(message.get_sender_contact().addr) 
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
               try:
                  client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
                  await client.connect()
                  await client.get_dialogs()
                  if key.lstrip('-').isnumeric():
                     target = int(key)  
                  else:
                     target = key
                  tchat = await client(functions.messages.GetPeerDialogsRequest(peers=[target] ))
                  ttitle = 'Unknown'
                  #extract chat title  
                  if hasattr(tchat,'chats') and tchat.chats:
                     ttitle = tchat.chats[0].title
                  else:
                     if hasattr(tchat,'users') and tchat.users:
                        ttitle = tchat.users[0].first_name
                  sin_leer = tchat.dialogs[0].unread_count
                  limite = 5
                  load_history = False                                  
                  if payload and payload.lstrip('-').isnumeric():
                     if payload.isnumeric():
                        all_messages = await client.get_messages(target, limit = 10, ids = [int(payload)])
                     else:
                        all_messages = await client.get_messages(target, min_id = int(payload.lstrip('-')), max_id =int(payload.lstrip('-'))+10)
                        load_history = True
                  else:
                     all_messages = await client.get_messages(target, limit = sin_leer)
                  if sin_leer>0 or load_history:
                     all_messages.reverse()
                  m_id = -0
                  for m in all_messages:
                      if limite>=0:
                         mquote = ''
                         mservice = ''
                         file_attach = 'archivo'
                         no_media = True
                         html_buttons = ''   
                            
                         #check if message is a reply
                         if m and hasattr(m,'reply_to'):
                            if hasattr(m.reply_to,'reply_to_msg_id'):
                               mensaje = await client.get_messages(target, ids = [m.reply_to.reply_to_msg_id])                               
                               if mensaje:
                                  reply_text = ''  
                                  if hasattr(mensaje[0],'sender') and mensaje[0].sender and hasattr(mensaje[0].sender,'first_name') and mensaje[0].sender.first_name:
                                     reply_send_by = str(mensaje[0].sender.first_name)+": "
                                  else:
                                     reply_send_by = ""
                                  if hasattr(mensaje[0],'media') and mensaje[0].media:
                                     if hasattr(mensaje[0].media,'photo'):
                                        reply_text += '[FOTO]'
                                  if hasattr(mensaje[0],'document') and mensaje[0].document:
                                     reply_text += '[ARCHIVO]'      
                                  reply_text += str(mensaje[0].text)      
                                  mquote = '>'+reply_send_by+reply_text+'\n\n'
                                
                         #check if message is a system message       
                         if m and hasattr(m,'action') and m.action:
                            mservice = '_system message_\n'
                            
                         #extract sender name   
                         if m and hasattr(m,'sender') and m.sender and hasattr(m.sender,'first_name') and m.sender.first_name:
                            send_by = str(m.sender.first_name)+":\n"
                         else:
                            send_by = ""
                            
                         #check if message have buttons
                         if m and hasattr(m,'reply_markup') and m.reply_markup and hasattr(m.reply_markup,'rows'):                            
                            nrow = 0
                            html_buttons = '\n---\n'
                            for row in m.reply_markup.rows:                                
                                html_buttons += '\n'
                                ncolumn = 0
                                for b in row.buttons:
                                    if hasattr(b,'url') and b.url:
                                       html_buttons += '[[`'+str(b.text)+'`]('+str(b.url)+')] '
                                    else:
                                       html_buttons += '[`'+str(b.text)+' /c_'+str(m.id)+'_'+str(nrow)+'_'+str(ncolumn)+'`] '
                                    ncolumn += 1
                                html_buttons += '\n'
                                nrow += 1
                         
                         #check if message have document
                         if m and hasattr(m,'document') and m.document:
                            if m.document.size<512000:
                               file_attach = await client.download_media(m.document, message.get_sender_contact().addr)
                               replies.add(text = send_by+file_attach+"\n"+str(m.message)+html_buttons, filename = file_attach)
                            else:
                               if hasattr(m.document,'attributes') and m.document.attributes:
                                  if hasattr(m.document.attributes[0],'file_name'):
                                     file_attach = m.document.attributes[0].file_name
                                  if hasattr(m.document.attributes[0],'title'):
                                     file_attach = m.document.attributes[0].title
                               replies.add(text = send_by+str(m.message)+"\n"+str(file_attach)+" "+str(sizeof_fmt(m.document.size))+"\n/down_"+str(m.id)+html_buttons)
                            no_media = False
                            
                         #check if message have a photo   
                         if m and hasattr(m,'media') and m.media:
                            if hasattr(m.media,'photo'):
                               if m.media.photo.sizes[1].size<512000:
                                  file_attach = await client.download_media(m.media, message.get_sender_contact().addr)
                                  replies.add(text = send_by+str(file_attach)+"\n"+str(m.message)+html_buttons, filename = file_attach)
                               else:
                                  replies.add(text = send_by+str(m.message)+"\nFoto de "+str(sizeof_fmt(m.media.photo.sizes[1].size))+"/down_"+str(m.id)+html_buttons)
                               no_media = False
                            if hasattr(m.media,'webpage'):
                               if m.media.webpage:
                                  no_media = False
                                  replies.add(text = send_by+str(m.media.webpage.title)+"\n"+str(m.media.webpage.url)+html_buttons)
                               else:
                                  no_media = True
                               
                         
                         #send only text message
                         if m and no_media:
                            replies.add(text = mservice+mquote+send_by+str(m.message)+html_buttons)
                         if m:   
                            await m.mark_read()
                 
                         if m:
                            m_id = m.id
                            print('Leyendo mensaje '+str(m_id))
                         #client.send_read_acknowledge(entity=int(key), message=m)
                      else:
                         if not load_history:
                            replies.add(text = "Tienes "+str(sin_leer-2-5-limite)+" mensajes sin leer de "+str(ttitle)+"\n/more")
                         break
                      limite-=1
                  if sin_leer-limite<=0 and not load_history:
                     replies.add(text = "Estas al día con "+str(ttitle)+"\n/more")
                  if load_history:
                     replies.add(text = "Cargar más mensajes:\n/more_-"+str(m_id))
                  await client.disconnect()
               except:
                  code = str(sys.exc_info())
                  replies.add(text=code)
               break
    else:
       replies.add(text='Este no es un chat de telegram')

def async_load_chat_messages(message, replies, payload):
    """Load more messages from telegram in a chat"""
    loop.run_until_complete(load_chat_messages(message, replies, payload))

def job():
    print("do the job")


@simplebot.command
def echo(payload, replies):
    """Echoes back text. Example: /echo hello world"""
    replies.add(text = payload or "echo")


async def echo_filter(message, replies):
    """Write direct in chat with T upper title to write a telegram chat"""
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para enviar mensajes, use los comandos:\n/login SUNUMERO\no\n/token SUTOKEN para iniciar, use /help para ver la lista de comandos.')
       return
    if message.get_sender_contact().addr in chatdb and str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
               try:                  
                  client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)                
                  await client.connect()
                  await client.get_dialogs()
                  if key.lstrip('-').isnumeric():
                     target = int(key)
                  else:
                     target = key
                  if message.filename:
                     if message.filename.find('.aac')>0:
                        await client.send_file(target, message.filename, voice_note=True)
                     else:
                        await client.send_file(target, message.filename, caption = message.text)
                  else:
                     await client.send_message(target,message.text)
                  await client.disconnect()
                  break
               except:
                  await client(SendMessageRequest(target, message.text))
                  code = str(sys.exc_info())
                  replies.add(text=code)
    else:
       replies.add(text='Este chat no está vinculado a telegram')

@simplebot.filter
def async_echo_filter(message, replies):
    """Write direct in chat bridge to write to telegram chat"""
    loop.run_until_complete(echo_filter(message, replies))
    
async def send_cmd(message, replies, payload):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para enviar mensajes, use los comandos:\n/login SUNUMERO\no\n/token SUTOKEN para iniciar, use /help para ver la lista de comandos.')
       return
    if message.get_sender_contact().addr in chatdb and str(message.chat.get_name()) in chatdb[message.get_sender_contact().addr].values():
       for (key, value) in chatdb[message.get_sender_contact().addr].items():
           if value == str(message.chat.get_name()):
               try:                  
                  client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)                
                  await client.connect()
                  await client.get_dialogs()
                  if key.lstrip('-').isnumeric():
                     target = int(key)
                  else:
                     target = key
                  if message.filename:
                     if message.filename.find('.aac')>0:
                        await client.send_file(target, message.filename, caption = payload, voice_note=True)
                     else:
                        await client.send_file(target, message.filename, caption = payload)
                  else:
                     await client.send_message(target,payload)
                  await client.disconnect()
                  break
               except:
                  await client(SendMessageRequest(target, payload))
                  code = str(sys.exc_info())
                  replies.add(text=code)
                
def async_send_cmd(message, replies, payload):
    """Send command to telegram chats. Example /b /help"""
    loop.run_until_complete(send_cmd(message, replies, payload))
    loop.run_until_complete(load_chat_messages(message=message, replies=replies, payload=''))

async def search_chats(bot, message, replies, payload):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para buscar chats, use los comandos:\n/login SUNUMERO\no\n/token SUTOKEN para iniciar, use /help para ver la lista de comandos.')
       return
    try:
        if not os.path.exists(message.get_sender_contact().addr):
           os.mkdir(message.get_sender_contact().addr)
        client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)                
        await client.connect()
        all_chats = await client.get_dialogs()
        id_chats = {}    
        for d in all_chats:
            id_chats[d.entity.id] = ''
        resultados = await client(functions.contacts.SearchRequest(q=payload, limit=5))       
        for rchat in resultados.chats:
            #await client.get_entity(rchat)
            if hasattr(rchat, 'photo'):
               profile_img = await client.download_profile_photo(rchat, message.get_sender_contact().addr)
            else:
               profile_img = ''
            if rchat.id in id_chats:
               replies.add(text = 'Grupo/Canal\n\n'+str(rchat.title)+'\nCargar: /load_'+str(rchat.username), filename = profile_img)
            else:
               replies.add(text = 'Grupo/Canal\n\n'+str(rchat.title)+'\nUnirse: /join_'+str(rchat.username)+'\nVista previa: /preview_'+str(rchat.username), filename = profile_img)            
        for ruser in resultados.users:
            #await client.get_entity(ruser)
            if hasattr(ruser, 'photo'):
               profile_img = await client.download_profile_photo(ruser, message.get_sender_contact().addr)
            else:
               profile_img =''
            if ruser.id in id_chats:
               replies.add(text = 'Usuario\n\n'+str(ruser.first_name)+'\nCargar: /load_'+str(ruser.username), filename = profile_img)
            else:
               replies.add(text = 'Usuario\n\n'+str(ruser.first_name)+'\nVista previa: /preview_'+str(ruser.username), filename = profile_img)
            
        await client.disconnect()         
    except:
        code = str(sys.exc_info())
        replies.add(text=code)
                
def async_search_chats(bot, message, replies, payload):
    """Make search for public telegram chats. Example: /search delta chat"""
    loop.run_until_complete(search_chats(bot, message, replies, payload))


async def join_chats(bot, message, replies, payload):
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para buscar chats, use los comandos:\n/login SUNUMERO\no\n/token SUTOKEN para iniciar, use /help para ver la lista de comandos.')
       return
    try:                  
        client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)                
        await client.connect()
        await client.get_dialogs()
        if payload.find('/joinchat/')>0:
           invite_hash = payload.rsplit('/', 1)[-1]
           await client(ImportChatInviteRequest(invite_hash))           
        else:
           uname = payload.replace('@','')
           uname = uname.replace(' ','_')
           await client(JoinChannelRequest(uname))
        await client.disconnect()
        replies.add(text='Se ha unido al chat '+payload)
    except:
        code = str(sys.exc_info())
        replies.add(text=code)
                
def async_join_chats(bot, message, replies, payload):
    """Join to telegram chats by username or private link. Example: /join @usernamegroup
    or /join https://t.me/joinchat/invitehashtoprivatechat"""
    loop.run_until_complete(join_chats(bot = bot, message = message, replies = replies, payload = payload))
    loop.run_until_complete(updater(bot=bot, payload=payload.replace('@',''), replies=replies, message=message))
    if message.get_sender_contact().addr in logindb:
       async_save_delta_chats(replies = replies, message = message)

async def preview_chats(bot, payload, replies, message):
    try:
        if message.get_sender_contact().addr not in logindb:
           replies.add(text = 'Debe iniciar sesión para visualizar chats!')
           return
        if not os.path.exists(message.get_sender_contact().addr):
           os.mkdir(message.get_sender_contact().addr)
        contacto = message.get_sender_contact()
        client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
        await client.connect()
        await client.get_dialogs()
        if message.get_sender_contact().addr not in chatdb:
           chatdb[message.get_sender_contact().addr] = {}
        uid = payload.replace('@','')
        uid = uid.replace(' ','_')
        if str(uid) not in chatdb[message.get_sender_contact().addr]:
           replies.add(text = 'Creando chat...')        
           pchat = await client.get_entity(uid)
           if hasattr(pchat, 'title') and pchat.title:
              ttitle =  str(pchat.title)
           else:
              if hasattr(pchat, 'first_name') and pchat.first_name:
                 ttitle = str(pchat.first_name)
              else:  
                 ttitle = 'Preview of'
           titulo = str(ttitle)+' ['+str(uid)+']'             
           chat_id = bot.create_group(titulo, [contacto])
           try: 
               img = await client.download_profile_photo(uid, message.get_sender_contact().addr)
               if img and os.path.exists(img): 
                  chat_id.set_profile_image(img)
           except:
               print('Error al poner foto del perfil al chat:\n'+str(img))   
           chatdb[message.get_sender_contact().addr][str(uid)] = str(chat_id.get_name())
           replies.add(text = 'Se ha creado una vista previa del chat '+str(ttitle))
           replies.add(text = "Cargar más mensajes\n/more_-0", chat = chat_id)
        await client.disconnect()
    except:
        code = str(sys.exc_info())
        print(code)
        replies.add(text=code)

def async_preview_chats(bot, payload, replies, message):
    """Preview chat with out join it, using the username like: /preview @username"""
    loop.run_until_complete(preview_chats(bot, payload, replies, message))
    if message.get_sender_contact().addr in logindb:
       async_save_delta_chats(replies = replies, message = message)                        

def eval_func(bot: DeltaBot, payload, replies, message: Message):
    """eval and back result. Example: /eval 2+2"""
    try:
       code = str(eval(payload))
    except:
       code = str(sys.exc_info())
    replies.add(text=code or "echo")

def start_updater(bot: DeltaBot, payload, replies, message: Message):
    """run schedule updater to get telegram messages. /start"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, "interval", seconds=10)
    scheduler.start()

async def c_run(payload, replies, message):
    """Run command inside a TelegramClient. Example: /c client.get_me()"""
    if message.get_sender_contact().addr not in logindb:
       replies.add(text = 'Debe iniciar sesión para ejecutar comandos!')
       return
    try:
       replies.add(text='Ejecutando...')
       client = TC(StringSession(logindb[message.get_sender_contact().addr]), api_id, api_hash)
       await client.connect() 
       await client.get_dialogs()
       code = str(await eval(payload))
       if replies: 
          replies.add(text = code)
       await client.disconnect()
    except:
       code = str(sys.exc_info())
       print(code)
       if replies:
          replies.add(text=code or "echo")
            
def async_run(payload, replies, message):
    """Run command inside a TelegramClient. Example: /c client.get_me()"""
    loop.run_until_complete(c_run(payload, replies, message))  
            
def sizeof_fmt(num: float) -> str:
    """Format size in human redable form."""
    suffix = "B"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)

class TestEcho:
    def test_echo(self, mocker):
        msg = mocker.get_one_reply("/echo")
        assert msg.text == "echo"

        msg = mocker.get_one_reply("/echo hello world")
        assert msg.text == "hello world"

    def test_echo_filter(self, mocker):
        text = "testing echo filter"
        msg = mocker.get_one_reply(text, filters=__name__)
        assert msg.text == text

        text = "testing echo filter in group"
        msg = mocker.get_one_reply(text, group="mockgroup", filters=__name__)
        assert msg.text == text
