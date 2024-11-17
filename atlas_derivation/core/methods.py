from rucio.client import didclient, scopeclient

def init_clients():
    clients = {
        'did': didclient.DIDClient(),
        'scope': scopeclient.ScopeClient()
    }
    return clients