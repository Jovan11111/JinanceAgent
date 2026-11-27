# AGENTS.md (not really but whats supposed to be in it)
- You are an expert software engineer that has been implementing application all their life. 
- You are in charge of implementing the application that is described at the bottom.
- You are the best at this, and you have unlimited time and resources to be sure that everything that is asked is implemented correctly.
- DO NOT MAKE ANY MISTAKES.
- For backend: the virtual environment already exists, its backend/venv. If you want to run something, do not make a separate venv, user this one.
- If implementing all at once it too complicated, do only a part, give me a report, and write everything you did in a file so you can continue.

# Development plan
Document describing what is supposed to be implemented in the application that is being built
## Application
Application is called Jinance Agent. Its an AI agent that is used to gather all the relevant information about finances.
Backend part is used as an interface to an LLM, and for definitions od tools and creating of tools needed for the agent to work properly. Backend can be run separately, through main.py file, while using the CLIInterface class that is responsible for clean CLI interface.

# Backend
- The backend will be explained through classes that exist, and their responsibilities
- Names of the files are not final, if you think there are more sensible names , rename the files.
## Database interface
Class that communicates with the database. All communication is done through models. When data is loaded, it is loaded into models, when data is written into database, it is done through models. Models are in the models folder. The database is explained in Database part, and some function names are already added in the database_backend.py file.
## CLI interface
If someone goes into backend folder and runs main.py, they can run the app in terminal mode, through CLI, and not through frontend. CLI interface is responsible for everything looking clean in CLI, and it is responsible for collecting input through terminal and showing messages in terminal. It should welcome the user, be sure that Agent: is green and You: is red. It doesn't need to load old messages, it doesn't need to show all chats, and it doesn't need to show images, but chats created should be remembered and visible in frontend.
## LLM interface
Class responsible for communicating with the LLM. Simplest possible way to send message to LLM is shown in the file, and this is just a showcase, not something that should be kept. IMO LLMInterface should be abstract, and then we should create GROQLLMInterace which will communicate with GROQ (current). this leaves us option to maybe have other LLM clients in the future. I want this to be implemented in the best possible way. It should have a loop that goes on until the prompt in answered completely. I am leaving you to fulfill the implementation so its the best possible.
## Frontend interface
Class responsible for communicating with the frontend. It receives requests from the frontend and returns what is asked. Should be simple. Possibly implemented in fastapi (this is my guess, it makes sense.)
## main file
Used only when user wants to run terminal mode. has no logic and is used only for instantiating CLI interface, and running it.
## Tools folder
Folder where all the tools are implemented. The tools I came up with right away are Graph tool that need to generate graphs with matplotlib and save the graphs in db/images. The other tool That I came up with receives .md data and creates a PDF report from it. I already implemented md -> pdf generation in root/../Jinance. Yahoo tool if for communicating with the MCP. I haven.t researched how good this MCP is and how to communicate with it but this makes the most sense to me. 
## instructions files folder
This is where skills and instruction files will be, so .md files. Currently I just want everything working, so I want this to be a simple system instruction that says "you are jinance agent, personal finance assistant." I will write this file in more detail later.
## config
Contains config data. name of the model used (openai/gpt-oss-120b for example), name of the client used (GROQ for example). Basically all the non secret information used to set up backend. config should be a class from which you can retrieve data, like a static data class or something. Additionally, it should have method "load_skill(skill_name: str)", and load_instruction_file(file_name: str), for loading md files into prompt from instruction files folder.

# Frontend
- Simple web application that can be run locally on any computer with minimal set up.
- One page only, with two parts
- First part: chat choosing side panel. On the left side user sees all of their chats, and can select one by clicking on it. Titles of the chats are shown, one under the other. The user can delete chats (think of a way that looks nice).
- Second part: active chat, on load the active chat is the latest one. Has the input at the bottom where the user send the message, and the "send button". User can send a message by clicking Enter as well, while input is active. Main part of the active chat is messages. User messages are on the right, agent messages are on the left. When the chat is opened, and when the new message is sent, the chat is automatically scrolled all the way to the bottom. 
- Performance: Application is run only locally, so I don't think it will be too slow to load all messages always. Additionally the app is simple. If it will be slow to load all messages, implemented infinite scroll, with the first 50 messages loading immediately, and the next only after scrolling up, and then again etc. Implement this only if the performance will suffer a lot with loading all messages.
- The app is slick, simple, dark theme, with green themes. Mostly, the app should be black/gray, with some simple green outlines to give contrast.
- The app supports agent sending images, but user can't send images. Messages are shown with a simple img tag, with source being a place where backend generated the image. since this is locally run app, all images will be generated in db/images folder.
## Technical requirements
- As simple as possible to install and use. Simplest technologies that (possibly) don't need to be installed separately if someone wants to run the application (for example, if app is made in Angular, and someone with no npm want to run it, they can't. We don't want that)


# Database
- Used to save information about chat history. 
- Tables are described as simple as possible. If anything else is needed add it: Chats, name of the chat and its ID. Messages, with fields type (user, agent), chat, time, content.
- implemented in sqlite. 
- Frontend asks the backend, and backend communicates with database through database interface
- No users table. app is made to be used on one computer, by one user, so no need for users.

# Additional info
- write code as simple as possible. Code that is easy to understand and maintain.
- code shouldn't be "AI SLOP". No need for unnecessary code.
- Before implementing ask all the questions you have. I will provide good answers. If you are not happy with the answers, ask again. It is very important that you are completely sure of everything you are supposed to do, and understand everything completely. Grill me, interview me, ask me all the questions you have before starting
- Be critical, if you notice any decisions that are not good, not make sense, or if you notice a simpler or better way to organize something, ask me. We can then discuss it. We are a team, if you notice that something is stupid, say it so I can decide in which way should you implement it
- When user closes a chat, or shuts down an application, that chat is updates in the database. Its title should be generated by an LLM as a "as short as possible title explaining what this chat is about."
- If the user uses the same chat for a long time, that chat should be compacted, and summary should be saved. I'm not sure how to implement this, but it should be done every 20or so messages. If you think it should be done more or less often say it. User should see the message that their chat was compacted.
- If the user sends /skill_name, in the input that text should become green, and the skill should be loaded if it exists. If it doesn't, user should know. Possibly, I wish to download other people skills and use them if that is possible, if not tell me.
