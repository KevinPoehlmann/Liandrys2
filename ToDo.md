# Project TODO & Notes

## ✅ Tasks to Do
### General Tasks ###
- [x] Make a better readme file with chatgpt
- [x] Make type hints work in database
### Functionality ###
- [x] Inject combo into simulation
- [ ] Make damage calculation handle most things
    - [x] Implement distance
    - [ ] Make abilities work
        - [x] Implement delay on ability damage
        - [x] Make cooldowns matter
        - [x] Make simple damage abilities work
            - [x] Implement simple ability usage
            - [x] Create simple abilities for testing
            - [x] Tests for simple ability usage
        - [x] Make simple dot abilities work
            - [x] Implement simple dot ability usage
            - [x] Create simple dot abilities for testing
            - [x] Tests for simple dot ability usage
        - [x] Make simple healing abilities work
            - [x] Implement simple healing ability usage
            - [x] Create simple healing abilities for testing
            - [x] Tests for simple healing ability usage
        - [x] Make simple shielding abilities work
            - [x] Implement simple shielding ability usage
            - [x] Create simple shielding abilities for testing
            - [x] Tests for simple shielding  bility usage
        - [ ] Make harder abilities work
            - [ ] Implement harder ability usage
            - [ ] Create harder abilities for testing
            - [ ] Tests for harder ability usage
        - [ ] Implement pets
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
### Admin Functions ###
- [ ] Make Dataset updateable
- [ ] Make Abilities editable in the editor
- [ ] Make Passives editable in the editor
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
    - login data for the mongo express admin and pass (default)

---
*This file is meant to keep track of development tasks and useful notes for future reference.*

