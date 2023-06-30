class MatchQueryBuilder(object):
	def __init__(self,playerQueries,teamQueries):
		self.aditionalQuery = {}
		self.complement = {}
		self.query = {"aggs":self.complement}
		self.chainnedQueries = {}
		self.queriesNames = ["GM","qtype","dateRange","platformId"]
		self.playerQueries = playerQueries
		self.teamQueries = teamQueries
		self.queryDependency = {}
		self.setGameMode()
		self.setQType()
		self.setDate()

	def setGameMode(self,gameMode=None):
		query = {"match_all":{}}
		if gameMode is not None:
			query = {"terms":{"info.gameMode": gameMode}}
		self.chainnedQueries["GM"] = query
		pass

	def setQType(self,qType=None):
		query = {"match_all":{}}
		if qType is not None:
			query = {"terms":{"info.queueId": qType}}
		self.chainnedQueries["qType"] = query
		pass

	def setDate(self,dateRange=None):
		query = {"match_all":{}}
		if dateRange is not None:
			query = {"range": {"info.gameCreation": {"gte": dateRange[0],"lte": dateRange[1]}}}
		self.chainnedQueries["dateRange"] = query
		pass

	def setPlatformId(self,platformId=None):
		query = {"match_all":{}}
		if platformId is not None:
			query = {"terms": {"info.platformId": platformId}}
		self.chainnedQueries["platformId"] = query
		pass

	def addQuery(self,name,query, dependency):
		self.aditionalQuery[name] = query
		self.queryDependency[name] = dependency
		pass

	
	def buildQuery(self):
		stackRef = self.complement 
		for qName in self.chainnedQueries:
			stackRef[qName] = {"filter":self.chainnedQueries[qName], "aggs": {}}
			stackRef = stackRef[qName]["aggs"]

		stackRef["players_query"] = self.playerQueries.buildQuery()
		stackRef["teams_query"] = self.teamQueries.buildQuery()
		stackRef["match_query"] = {"filter":{"match_all":{}},"aggs":{}}
		stackRef = stackRef["match_query"]["aggs"]
		for qName in self.aditionalQuery:
			stackRef[qName] = self.aditionalQuery[qName]

		return self.query

	def parseQueryResult(self,qResult):
		result = {}
		stackRef = qResult["aggregations"]
		for qName in self.chainnedQueries:
			stackRef = stackRef[qName]
		matchRes = stackRef["match_query"]
		for qName in self.aditionalQuery:
			result[qName] = {}
			aux = matchRes[qName]
			for dep in self.queryDependency[qName]:
				aux = aux[dep]

			result[qName] = aux
				

		playerRes = self.playerQueries.parseQueryResult(stackRef["players_query"])
		teamRes = self.teamQueries.parseQueryResult(stackRef["teams_query"])
		return result | playerRes | teamRes




class MatchPlayerSubQueryBuilder(object):
	def __init__(self):
		self.aditionalQuery = {}
		self.complement = {}
		self.baseQuery = {"nested": {"path": "info.participants"},"aggs":self.complement}
		self.chainnedQueries = {}
		self.queriesNames = ["players_winner","players_team"]
		self.queryDependency = {}
		self.setWinner()
		self.setTeam()

	def setWinner(self, win=None):
		query = {"match_all":{}}
		if win is not None:
			query = {"term":{"info.participants.win": win}}
		self.chainnedQueries["players_winner"] = query

	def setTeam(self, teamId=None):
		query = {"match_all":{}}
		if teamId is not None:
			query = {"terms":{"info.participants.teamId": teamId}}
		self.chainnedQueries["players_team"] = query

	def addQuery(self,name,query,dependency):
		self.aditionalQuery[name] = query
		self.queryDependency[name] = dependency
		pass

	def buildQuery(self):
		stackRef = self.complement 
		for qName in self.chainnedQueries:
			stackRef[qName] = {"filter":self.chainnedQueries[qName], "aggs": {}}
			stackRef = stackRef[qName]["aggs"]

		for qName in self.aditionalQuery:
			stackRef[qName] = self.aditionalQuery[qName] 
		return self.baseQuery

	def parseQueryResult(self,qResult):
		result = {}
		stackRef = qResult
		for qName in self.chainnedQueries:
			stackRef = stackRef[qName]

		for qName in self.aditionalQuery:
			result[qName] = {}
			aux = stackRef[qName]
			for dep in self.queryDependency[qName]:
				aux = aux[dep]

			result[qName] = aux
		return result




class MatchTeamSubQueryBuilder(object):
	def __init__(self):
		self.aditionalQuery = {}
		self.chainnedQueries = {}
		self.complement = {}
		self.queryDependency = {}
		self.baseQuery = {"nested": {"path": "info.teams"},"aggs":self.complement}
		self.queriesNames = ["team_winner","team_color"]
		self.setWinner()
		self.setTeam()

	def setWinner(self, win=None):
		query = {"match_all":{}}
		if win is not None:
			query = {"term":{"info.teams.win": win}}
		self.chainnedQueries["team_winner"] = query

	def setTeam(self, teamId=None):
		query = {"match_all":{}}
		if teamId is not None:
			query = {"terms":{"info.teams.teamId": teamId}}
		self.chainnedQueries["team_color"] = query

	def addQuery(self,name,query,dependency):
		self.aditionalQuery[name] = query
		self.queryDependency[name] = dependency
		pass

	def buildQuery(self):
		stackRef = self.complement 
		for qName in self.chainnedQueries:
			stackRef[qName] = {"filter":self.chainnedQueries[qName], "aggs": {}}
			stackRef = stackRef[qName]["aggs"]

		for qName in self.aditionalQuery:
			stackRef[qName] = self.aditionalQuery[qName] 
		return self.baseQuery

	def parseQueryResult(self,qResult):
		result = {}
		stackRef = qResult
		for qName in self.chainnedQueries:
			stackRef = stackRef[qName]

		for qName in self.aditionalQuery:
			result[qName] = {}
			aux = stackRef[qName]
			for dep in self.queryDependency[qName]:
				aux = aux[dep]

			result[qName] = aux
		return result