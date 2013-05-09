from datetime import datetime

import atom.data
import gdata.calendar.data
import gdata.calendar.client
from BeautifulSoup import BeautifulSoup, Tag
import mechanize

CREDS = {'uname':'ece7361', 'pass':''}
ECLASS_URL = "https://eclass.upatras.gr"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
GOOGLE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S+03:00"
AUTHENTICATION = {'uname': 'eclass.to.calendar@gmail.com', 'pass': '123!@#abc'}
SUBMITTED_STRING = "[SUBMITTED]"

def contains_a(soup, tag, attr=None):
    if len(soup.contents) == 1 and isinstance(soup.contents[0], Tag) \
       and soup.contents[0].name == tag:
        if attr is not None:
            return attr in soup.contents[0].attrs
        else:
            return True

    return False


def clear_events(authentication=AUTHENTICATION):
    client = gdata.calendar.client.CalendarClient(source='fakedrake-eclasscalendar')

    if isinstance(authentication, dict):
        client.ClientLogin(authentication['uname'], authentication['pass'], client.source)
    else:
        raise TypeError("Authentication object not meeting my expectations.")


    feed = client.GetCalendarEventFeed()
    for e in feed.entry:
        client.Delete(e)


class Subject(object):
    """ A subject with deadlines in it.
    """

    def __init__(self, html):
        """ Just give it a name and we are good.
	"""
        self.html = html
        self.title = html.contents[0].text
        self.deadlines = []

    def calendar_sync(self, authentication=AUTHENTICATION):
        """Upload all unuploaded events."""

        for d in self.deadlines:
            d.maybe_upload(authentication)

    @staticmethod
    def is_subject(soup):
        return soup.name == "tr" and contains_a(soup, "td", ("class", "sub_title1"))


class Deadline(object):
    """ A deadline
    """

    def __init__(self, html, subject):
        """ Provide the html and we will do the rest.
	"""
        self.html = html
        self.title, self.deadline_text = [i.text for i in html.findAll("b")][:2]
        self.subject = subject

        id_off = dict(html.find("a").attrs)['href'].find('?')
        self.url =  dict(html.find("a").attrs)['href']
        self.uniquie_id = self.url[id_off:]

        self.submitted = "NOT submitted" not in html.text

    def datetime(self):
        return datetime.strptime(self.deadline_text, TIME_FORMAT)

    def matches(self, gcal_event):
        """See if this is is the same as a google calendar event."""
        return gcal_event.content.text and self.uniquie_id in gcal_event.content.text

    def full_title(self):
        """The title to be uploaded to google."""
        submitted_str = ""
        if self.submitted:
            submitted_str = SUBMITTED_STRING

        return "%s%s: %s" % (submitted_str, self.subject.title, self.title)

    def full_content(self):
        """The full content to be uploaded to google"""
        return "Deadline url: %s \n Unique id: %s" % (self.url, self.uniquie_id)

    def full_location(self):
        """Location to be uploaded to google"""
        return self.url

    def maybe_update(self, event, client):
        old_title = event.title.text
        if self.submitted and SUBMITTED_STRING not in old_title:
            print "Marking '%s' as submitted!" % old_title
            event.title.text = SUBMITTED_STRING + old_title
            client.Update(event)

    def maybe_upload(self, authentication=AUTHENTICATION):
        """If not already uploaded upload the deadline."""
        client = gdata.calendar.client.CalendarClient(source='fakedrake-eclasscalendar')

        if isinstance(authentication, dict):
            client.ClientLogin(authentication['uname'], authentication['pass'], client.source)
        else:
            raise TypeError("Authentication object not meeting my expectations.")

        feed = client.GetCalendarEventFeed()
        for e in feed.entry:
            if self.matches(e):
                self.maybe_update(e, client)
                return None

        event = gdata.calendar.data.CalendarEventEntry()
        event.title = atom.data.Title( text=self.full_title() )
        event.content = atom.data.Content( text=self.full_content() )
        event.where.append( gdata.calendar.data.CalendarWhere(value=self.full_location()) )

        start_time = self.datetime().strftime(GOOGLE_TIME_FORMAT)

        event.when.append(gdata.calendar.data.When(start=start_time))

        print "Uploading event '%s' at %s..." % (self.full_title(), start_time)
        return client.InsertEvent(event)


    @staticmethod
    def is_deadline(soup):
        return soup.name == "tr" and contains_a(soup, "td") and contains_a(soup.contents[0], "ul", ("class", "custom_list"))


class Eclass(object):
    """ Interaction with eclass.
    """

    def __init__(self, url=ECLASS_URL, creds=CREDS):
        """ Set the url and credentials.
	"""
        self.url = url
        self.creds = creds



    def _login_html(self):
        """The page immediately after login."""
        br = mechanize.Browser()
        br.open(self.url)
        br.select_form(nr=2)

        for k,v in CREDS.iteritems():
            br[k] = v

        response = br.submit()
        return response.read()

    def _deadlines_html(self):
        """The deadlines box."""

        return [l for l in self._login_html().split("\n") if l.find("Deadline") > 0][0]


    def subjects(self):
        """A list of subject objects found for pending deadlines."""

        soup = BeautifulSoup(self._deadlines_html())
        ret = []
        for t in soup.table:
            if Subject.is_subject(t):
                ret.append(Subject(t))

            if Deadline.is_deadline(t):
                ret[-1].deadlines.append(Deadline(t, ret[-1]))

        return ret

if __name__ == "__main__":

    eclass = Eclass()
    subjects = eclass.subjects()

    for s in subjects:
        print s.title
        for d in s.deadlines:
            print "\t",d.title, ":", d.datetime()

        s.calendar_sync()
