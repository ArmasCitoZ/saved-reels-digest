# TikTok export fixture

An invented, trimmed `user_data_tiktok.json` with the shape TikTok produces with
*Settings → Account → Download your data → JSON*. Video ids are made up
(`74000000000000000NN`); no real account data is stored here.

It covers three favorites (one listed twice, one with an unparseable date and the
`tiktok.com/@user/video/<id>` link form) and a liked video under `Like List` that
must be ignored: only Favorites are TikTok's "saved" videos.
