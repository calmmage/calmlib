Help me design a system for myself.
I am a python dev
Oftentimes I learn some cool library, or create a one of my own. Draft some cool
usecases for myself, that are convenient.
Then I will forget about it / forget how to use it
Or I will save it somewhere - never to discover again
That can be in a jupyter notebook...
And then I create a duplicate one / slightly different.
Or have to figure out everything again

I need a system and a protocol.
What I want to be able to do:

1) run a "remind()" command.
   That will show me compilation of all the commands i learn.
   have 1 or 2 main sections: main external libs, main custom libs
   and several mentions of secondary sections - just gy broad group mentions (
   e.g. web dev or api or meta etc..)
2) run a "remind(keyword)" command. That will show me info about a specific
   topic
   for example remind('tqdm') or remind('matplotlib') or remind ('gpt')
   And I want to get all my snippets related to that topic - for quick usage

Regarding the interface, i want to be able to:

- just create / drop a file in my 'dev/examples' folder
- for it to auto-pick some
- send a message to gpt / telegram bot in a free form and for it to figure out
  the rest, put it in place and so that it works

- attach tags -> the ones that are going to be used for search
- make gpt suggest tags for me
- make my bot come back to me and clarify if I want more tags attached

feature(s):

- display highlighted code, ready for copy (in jupyter / python console /
  output)
- auto-copy into buffer? is that possible in python?
- run a supplementary gpt feature - attach result in the end

structure:

I want to have 2-3 folders:
inbox/ (for all new patterns)
secondary/ (for the libs that are cool, but are situational to use)
main/ (for the code libs examples?)

Maybe something else as well.

I'm still figuring out the folder structure..
and file naming policy
probably folder should be like group name
and file name - all tags
