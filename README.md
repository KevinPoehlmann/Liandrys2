# Liandrys2

Liandrys2 is a web app designed to calculate and compare damage differences in League of Legends champion matchups, factoring in items, ability combinations, runes, and summoner spells.

## 🚀 Features

### **User Features**
- Calculate damage done by a champion to another based on selected runes, summoner spells, items, and ability combinations.
- Compare results across different setups, champions, and patches.

### **Admin Features**
- View a structured representation of the database.
- Update database to the latest patch using a web scraper.
- Manually manipulate data to transform textual inputs into structured calculations.

## 🛠️ Tech Stack
- **Backend:** Python with FastAPI
- **Frontend:** Vue with TailwindCSS (built with Vite)
- **Database:** MongoDB (asynchronously accessed via Motor)
- **Data Sources:** Riot API & web scraping (BeautifulSoup)
- **Containerization:** Docker & Docker Compose
- **Architecture:** Two frontends and two backends (user-facing & admin panel)

## ⚠️ Project Status
Liandrys2 is currently under development and not yet ready for production. Since some data manipulation is required for proper functionality, installation by others is not yet a focus.
**Not** in a functioning state right now!

## 🎯 Motivation & Learnings
This project was created to:
- Learn more about programming concepts, frameworks, and languages.
- Develop a unique tool for League of Legends theorycrafting, as no existing solutions fully meet these needs.
- Gain experience in backend/frontend development, database management, and web scraping.

Key learnings so far:
- **Planning is essential**—many things turned out to be more complex than expected! 😅
- Realizing the advantage of **Dependency Injection** when it comes to testing. 
- Gained hands-on experience with Docker, Vue, FastAPI, and MongoDB.

## 📸 Screenshots
(Screenshots will be added soon.)

## 📜 License
This project is licensed under the **Apache 2.0 License**—allowing open-source use while protecting against direct competition. See the [LICENSE](LICENSE) file for details.

---
*Liandrys2 is a personal project and is not affiliated with Riot Games.*

