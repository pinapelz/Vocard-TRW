restaurant_triggers = ["where should we eat", "where to eat", "what should we eat",
                     "restaurant recommendation", "food recommendation", "where eat", "where we eat",
                     "what's for dinner", "what's for lunch", "where for dinner", "where for lunch",
                     "food suggestions", "restaurant suggestions", "where should i eat", "where can we eat",
                     "what to eat", "dining recommendation", "place to eat", "good restaurant",
                     "food ideas", "eating out", "grab food", "get food", "hungry", "i'm hungry",
                     "we're hungry", "dinner ideas", "lunch ideas", "breakfast ideas", "meal ideas",
                     "craving food", "what restaurant", "pick a restaurant", "choose restaurant",
                     "recommend food", "suggest food", "food spots", "dining spots", "eat where", "where we getting food"]

banned_restaurants = {
    "danbo": "HELLSS NAHHH WE ARE NOT EATING THAT CUH. its not halal. long ass lines mid ass ramen",
    "hello nori": "brooooo srsly. out of all the japanese food u pick the one where you have to sit on hard ass stools and pay $9999 to eat 1 handroll",
    "saku": "lil brother. this is not only very disrespectfully all pork, we have gone there 1 billion times and the pricing is off the charts."
}

exaroton_start_triggers = ["start server", "boot up server", "start the diddly party"]
exaroton_status_triggers = ["server status", "is the server online", "server online", "check server", "diddly party status"]

SERVER_STATUS = {
    0: "OFFLINE",
    1: "ONLINE",
    2: "STARTING",
    3: "STOPPING",
    4: "RESTARTING",
    5: "SAVING",
    6: "LOADING",
    7: "CRASHED",
    8: "PENDING",
    9: "TRANSFERRING",
    10: "PREPARING"
}