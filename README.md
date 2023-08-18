# Household manager bot

A telegram bot built for hosting on [deta.space](https://deta.space/), using a webhook for minimal upkeep costs. Currently supports a point system for tracking points (collected e.g. by doing housework) and listing and redeeming rewards with said points.

### Context
We use [Nipto](https://nipto.app/) to keep track of housework and to collect points while doing chores. Nipto has a competitive feature where the winner of each week can get a reward from the losers, but we wanted to be able to use our points on rewards as they were accumulated, without the competitive element. With this app, we manually put in the points we acquire each week, and spend them on rewards as we wish. It's motivating, and we've stopped arguing about chores :)

### Setup
Should be hosted on deta.space. You need a [Telegram bot token](https://core.telegram.org/bots/features#creating-a-new-bot). Add the token, and a space-delimited list of allowed usernames, as environment variables. Once the app is running, visit the /set_webhook path to connect the app to the bot.

Note that the app is set as public, so that the Telegram bot API can send messages to the webhook.