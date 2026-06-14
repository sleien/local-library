"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.book import (
    Asset,
    Book,
    BookTag,
    Comment,
    Copy,
    CoverCandidate,
    Tag,
    UserBook,
)
from app.models.loan import Loan, LoanFeedback, Person
from app.models.location import Location
from app.models.user import Household, HouseholdInvite, HouseholdMembership, User

__all__ = [
    "Asset",
    "Book",
    "BookTag",
    "Comment",
    "Copy",
    "CoverCandidate",
    "Tag",
    "UserBook",
    "Loan",
    "LoanFeedback",
    "Person",
    "Location",
    "Household",
    "HouseholdInvite",
    "HouseholdMembership",
    "User",
]
