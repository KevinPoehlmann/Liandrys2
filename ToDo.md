# Project TODO & Notes

## ✅ Tasks to Do
### General Tasks ###
- [x] Make a better readme file with chatgpt
- [x] Make type hints work in database
### Functionality ###
- [ ] Make abilities work
    - [ ] Make simple abilities work
        - [x] Implement simple ability usage
        - [ ] Create simple abilities for testing
        - [ ] Tests for simple ability usage
    - [ ] Make harder abilities work
        - [ ] Implement harder ability usage
        - [ ] Create harder abilities for testing
        - [ ] Tests for harder ability usage
    - [ ] Make complex abilities work
        - [ ] Implement complex ability usage
        - [ ] Create complex abilities for testing
        - [ ] Tests for complex ability usage
- [ ] Make passives work
    - [ ] Make simple passives work
        - [ ] Implement simple passive usage
        - [ ] Create simple passive for testing
        - [ ] Tests for simple passive usage
    - [ ] Make harder passives work
        - [ ] Implement harder passive usage
        - [ ] Create harder passive for testing
        - [ ] Tests for harder passive usage
    - [ ] Make complex passives work
        - [ ] Implement complex passive usage
        - [ ] Create complex passive for testing
        - [ ] Tests for complex passive usage
    - [ ] Make item passives work
        - [ ] Implement item passives
        - [ ] Create item passives for testing
        - [ ] Tests for item passives
- [ ] Make item actives work
    - [ ] Add item active choices in frontend
    - [ ] Make item actives work in backend
        - [ ] Implement item actives
        - [ ] Create item actives for testing
        - [ ] Tests for item actives
- [ ] Add Rune choice in simulation
- [ ] Add Summonerspell choice in simulation
- [ ] Update the web scraper
    - [ ] Update to new website
        - [ ] Change link
        - [ ] Check if anything else changed
    - [ ] Update to new Structures
        - [ ] Update to new Champion Structure
        - [ ] Update to new Item Structure
        - [ ] Update to new Rune Structure
        - [ ] Update to new Summonerspell Structure
- [ ] Make `Ability` editable in the editor
### Production ###
- [ ] Making the project ready for production
    - [ ] Add a disclaimer stating that your project isn’t affiliated with Riot Games.
    - [ ] Register the project through Riot’s Developer Portal.


## 🛠 Setup & Debugging Tips
- **Testing:**
    - cd backend
    - pytest
    - or pytest src/tests/*test_file.py*
- **Installation on raspberrypi:**
    - probably just use "docker-compose -f docker-compose.yml -f docker-compose.rpi.yml up -d
"
    - swap outcommented lines:
        - docker-compose: mongo image
        - database.py: client?
    - upload it to github
    - download project to raspberrypi
        - access raspberrypi via ssh: user and pw?
        - get some key from github to download it via ssh from the raspberry
        - donwload it
    - swap back lines and put it back on github
- **Common Issues:**
    - login data for the mongo express server in docker-compose file

---
*This file is meant to keep track of development tasks and useful notes for future reference.*

