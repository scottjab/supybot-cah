###
# Copyright (c) 2012, James Scott
# All rights reserved.
#   
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.schedule as schedule
import supybot.callbacks as callbacks

from random import randint, shuffle

import operator 

from cah import Game

import time

class Cah(callbacks.Plugin):
    """Add the help for "@plugin help Cah" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Cah, self)
        self.__parent.__init__(irc)
        self.games = {}

    class CahGame(object):
        """docstring for Game"""
        def __init__(self, irc, channel, numrounds = 5, voteRules = True):
            self.irc = irc
            self.channel = channel
            self.game = None
            self.canStart = False
            self.voting = False
            self.canStart = False
            self.roundRunning = False
            self.running =  False
            self.rounds = numrounds
            self.maxPlayers= 5
            self.players = []
            self.acceptingWhiteCards = False
            self.cardsPlayed = {}
            self.currentCzar = None
            self.czarOrder = None
            self.voteRules = voteRules

        def initGame(self):
            schedule.addEvent(self.startgame, time.time() + 60, "start_game_%s" % self.channel)

        ###### UTIL METHODS ##########

        def _formatWhiteCard(self, text):
            return ircutils.bold(ircutils.mircColor(text, bg="white", fg="black"))

        def _formatBlackCard(self, text):
            return ircutils.bold(ircutils.mircColor(text, bg="black", fg="white"))
      
        def _msg(self, recip, msg):
            self.irc.queueMsg(ircmsgs.privmsg(recip,msg))
        
        def _printBlackCard(self, recip):
            response = "Round %d of %d Question: %s"
            cah = self.game
            self._msg(recip, response % (cah.round ,cah.round_limit, self._formatBlackCard(cah.question.text)))

        def _msgHandToPlayer(self, nick):
            response = "Your cards: %s  Please respond with @playcard [channel if in pm] <number> [number]"
            enumeratedHand = []
            cah = self.game
            self._printBlackCard(nick)
            if self.voteRules and self.currentCzar == nick:
                self._msg(nick, ircutils.bold("YOU are the Card Czar, you get to pick the winner, so no hand for you!"))
            else:
                for position, card in enumerate(cah.players[nick].card_list):
                    enumeratedHand.append("%s: %s " % (position + 1, ircutils.bold(card.text)))
                self._msg(nick, self._formatWhiteCard(response % ', '.join(enumeratedHand)))

        def _displayPlayedCards(self):
            channel = self.channel
            responseTemplate = "%s: (%s)"
            responses = []
            response = "%s"
            for count, nick in enumerate(self.cardsPlayed.keys()):
                cards = ", ".join([self._formatWhiteCard(card.text) for card in self.cardsPlayed[nick]])
                responses.append(responseTemplate % (count + 1, cards))
            response = ";  ".join(responses)
            self._msg(channel, "Played White cards: %s" % response)

        def _findHighScore(self, scores):
            highscore = []
            for nick, score in scores.iteritems():
                if len(highscore) == 0:
                    highscore.append([nick, score])
                elif highscore[0][1] < score:
                    highscore = []
                    highscore.append([nick, score])
                elif highscore[0][1] == score:
                    highscore.append([nick, score])
            if len(highscore) > 0:
                return (highscore[randint(0, len(highscore) -1)], True)
            else:
                return (highscore[0], False)


        def _tallyVotes(self, votes):
            winningCanidate = []
            canidatesById = []
            for nick in self.cardsPlayed.keys():
                canidatesById.append(nick)

            for canidateNumber, count in votes.iteritems():
                canidate = canidatesById[int(canidateNumber)]
                count = int(count)
                if len(winningCanidate) == 0:
                    winningCanidate.append((canidate, count))
                elif winningCanidate[0][1] < count:
                    winningCanidate = []
                    winningCanidate.append((canidate, count))
                elif winningCanidate[0][1] == count:
                    winningCanidate.append((canidate, count))

            if len(winningCanidate) > 1:
                return (winningCanidate[randint(0, len(winningCanidate) -1)], True)
            return (winningCanidate[0], False)
                

        ###### END UTIL METHODS #######

        ###### PRE GAME LOGIC ########

        def startgame(self):
            #heh fix this
            game = self 
            if game.canStart:
                if len(game.players) < 2:
                    self._msg(channel, "I need more players.")
                else:
                    if game.voteRules:
                        game.nextCardCzar()
                    game.canStart = False
                    game.running = True
                    game.game = Game(game.players, game.rounds)
                    #start game logic
                    self.nextround()        

        ###### END PRE GAME LOGIC ######

        ###### START GAME LOGIC ########

        def playcard(self, nick, cardNumbers):
            game = self 
            cah = game.game
            cardlist = []
            cards = cah.players[nick].card_list
            for cardNum in cardNumbers:
                cardlist.append(cards[int(cardNum) - 1])
            self.cardsPlayed[nick] = cardlist
            if len(self.cardsPlayed) == len(self.players):
                try:
                    schedule.removeEvent("round_%s" % self.channel)
                except:
                    pass
                self.endround()

        def nextround(self):
            channel = self.channel
            game = self
            cah = game.game
            try:
                self.cardsPlayed = {}
                cah.next_round()
                #Print Black Card to channel.
                self._printBlackCard(self.channel)
                for nick in self.players:
                    self._msgHandToPlayer(nick)
                self._msg(channel, "The white cards have been PMed to the players, you have 60 seconds to choose.")
                self.acceptingWhiteCards = True
                #TODO: do we need a round flag?
                schedule.addEvent(self.endround, time.time() + 60, "round_%s" % channel)
            except Exception:
                #TODO: add no more round logic
                
                #playerScores = sorted(cah.score.iteritems(), key=operator.itemgetter(1), reverse=True)
                #scores = []
                winner = None
                formattedScores = []
                print cah.score
                winner = self._findHighScore(cah.score)
                for name, score in cah.score.iteritems():
                    formattedScores.append("%s: %d" % (name, score))
                self._msg(channel, "Game Over! %s is the Winner!  Scores: %s " % (winner[0][0], ", ".join(formattedScores)))


        def endround(self):
            channel = self.channel
            try:
                game = self
                if game.acceptingWhiteCards:
                    game.acceptingWhiteCards = False
                    self._msg(channel, "Card Submittion Completed.")
                    self._printBlackCard(channel)
                    self._displayPlayedCards()
                    if self.isVotingGame:
                        self.startcardvote()
                    else:
                        self.startcardczar()
                else:
                    self._msg(channel, "No round active.")
            except KeyError:
                self._msg(channel, "A Game is not running.")

        def roundwinner(self, winner):
            self.game.roundwinner(nick)
            self._msg(self.channel, "%s wins the round!" % ircutils.bold(winner))


        ###### END GAME LOGIC #########

        ###### CARD CZAR LOGIC ########

        def nextCardCzar(self):
            if self.czarOrder is None:
                self.czarOrder = shuffle(self.players)
            self.currentCzar = self.czarOrder.pop(0)
            self.czarOrder.append(self.currentCzar)



        def startcardczar(self):
            
            self._msg(self.channel, "%s is the card Czar! %s has 60 seconds to choose the winner", self.currentCzar)
            schedule.addEvent(self.randomczar, time.time() + 60, "czar_%s" % channel)


        def randomczar(self):
            self._msg("%s took too long to respond like an idiot, so I am choosing the winner." % self.currentCzar)
            endcardczar(randint(0, len(self.cardsPlayed)))

        def endcardczar(self, winner):
            #this could be better
            try:
                schedule.removeEvent("czar_%s" % channel)
            except:
                pass
            for count, nick in enumerate(self.cardsPlayed.keys()):
                if count == winner:
                    self.nextCardCzar()
                    self.roundwinner(nick)
                    self.nextround()




        ###### END CARD CZAR LOGIC ####


        ###### VOTING ##############

        def startcardvote(self):
            channel = self.channel
          
            game = self
            game.votes = {}
            game.voted = []
            game.voting = True
            self._msg(channel, "Please Vote on your favorite. @votecard <number> to vote, the entire channel can vote.")
            schedule.addEvent(self.stopcardvote, time.time() + 60, "vote_%s" % channel)
            



        def stopcardvote(self):
            
            #TODO: NOt quite done here
            if self.voting:
                game = self
                game.voting = False
                winner = self._tallyVotes(game.votes)
                print winner
                game.game.end_round(winner[0][0], self.cardsPlayed)
                game.voted = []
                self.roundwinner(winner[0][0])
                #game._msg(self.channel, "%s wins the round with %s" % (ircutils.bold(winner[0][0]), ircutils.bold(filledCard)))
                game.nextround()
         
        ###### END VOTING LOGIC ######

        def close(self):
            try:
                schedule.removeEvent("round_%s" % self.channel)
            except:
                pass
            try:
                schedule.removeEvent("vote_%s" % self.channel)
            except:
                pass
            try:        
                schedule.removeEvent("start_game_%s" % self.channel)
            except:
                pass  
    Class = CahGame

    ###### CHANNEL COMMANDS ######
    def forcestartgame(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        if channel in self.games:
            try:        
                schedule.removeEvent("start_game_%s" % self.channel)
            except:
                pass                
            self.games[channel].startgame()
        else:
            irc.reply("Game not running.")

    def playing(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        nick = msg.nick

        if channel in self.games:
            game = self.games[channel]

            if game.running == False:
                if nick in game.players:
                    irc.reply("You already are playing.")
                else:
                    if len(game.players) < game.maxPlayers:
                        game.players.append(nick)
                        irc.reply("Added, Spots left %d/%d.  Current Players %s" % (game.maxPlayers - len(game.players), game.maxPlayers, ', '.join(game.players)))
                    else:
                        irc.reply("Too many players")
                if len(game.players) > 1:
                    game.canStart = True
        else:
            irc.reply("Game not running.")



    def _startCah(self, irc, channel, rounds = 5, voting = True):
        if channel in self.games:
            irc.reply("There is a game running currently.")
        else:
            irc.reply("Who wants to play IRC Aganst Humanity? To play reply with: @playing", prefixNick=False)
            self.games[channel] = self.CahGame(irc, channel, numrounds)
            self.games[channel].initGame()

    # Traditional rules, Maybe switch this to arguements?        
    def cah(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        #TODO: this is prob needs fixing. 
        if len(args) < 1:
            numrounds = 5
        else:
            numrounds = int(args[0])
        self._startCah(irc, channel,rounds=numrounds, voting=False)
    #voting rules
    def iah(self, irc, msg, args):
        """Starts a cards against humanity game, takes
        an optional arguement of number of rounds"""
        channel = ircutils.toLower(msg.args[0])
        #TODO: this is prob needs fixing. 
        if len(args) < 1:
            numrounds = 5
        else:
            numrounds = int(args[0])
        self._startCah(irc, channel, rounds=numrounds)


            


    def scah(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        if channel in self.games:
            self.games[channel].close()
            self.games.pop(channel)
            irc.reply("Game stopped.")
        else:
            irc.reply("Game not running.")

    def playcard(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        nick = msg.nick
        if channel in self.games:
            game = self.games[channel]
            if not nick in game.players:
                irc.reply("You are not playing, GET OUT.")
            elif not game.acceptingWhiteCards:
                irc.reply("Not accepting white cards.")
            elif nick in game.cardsPlayed:
                irc.reply("You already played, GET OUT.")
            elif len(args) < game.game.question.answers:
                irc.reply("Hey shitbag I need more cards, this is a %s card question." % game.game.question.answers)
            elif len(args) > game.game.question.answers:
                if game.gane.question.answers == 1:
                    irc.reply("I only want one card you idiot.")
                irc.reply("Woah there tiger, I only need %s cards." % game.game.question.answers)
            elif len(args) == game.game.question.answers:
                game.playcard(nick, args)
        else:
            irc.reply("Game not running.")
        #TODO: Card decision logic

    def pickwinner(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        if channel in self.games:
            game = self.games[channel]
            if msg.nick == self.currentCzar:
                if len(args) < 0:
                    irc.reply("I need a fucking winner you idiot.")
                elif args[0] < 1 or args[0] > len(game.cardsPlayed()) - 1:
                     irc.reply("I need a value between 1 and %s" % len(game.cardsPlayed))
                else:
                    game.endcardczar(args[0])
            else:
                irc.reply("You are not the Czar GET OUT")
        else:
            irc.reply("Game not running.")


    def votecard(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        if channel in self.games:
            game = self.games[channel]
            try:
                vote = int(args[0])
                if game.voting:
                    if msg.nick in game.voted:
                        irc.reply("You already voted! This isn't Chicago!")
                    elif vote > len(game.cardsPlayed) or vote < 1:
                        raise ValueError 
                    else:
                        game.voted.append(msg.nick)
                        try:
                            game.votes[vote - 1] += 1
                        except KeyError:
                            game.votes[vote - 1] = 1
                        irc.reply("vote cast")
            except ValueError:
                irc.reply("I need a value between 1 and %s" % len(game.cardsPlayed))    
        else:
            irc.reply("A Game is not running, or the time is not to vote.")
    
    ####DEBUG VOTING REMOVE LATER#####
    # TODO: REMOVE THIS DEBUG CODE   # 
    def endvote(self, irc, msg, args):
        channel = ircutils.toLower(msg.args[0])
        if channel in self.games:
            try:
                schedule.removeEvent("vote_%s" % self.channel)
            except:
                pass
            self.games[channel].stopcardvote()
        else:
            irc.reply("Game not running.")


    ###### END CHANNEL COMMANDS ######

    
Class = Cah


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
