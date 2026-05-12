```
Explore the JavaScript files for other endpoints more deeply, extract the parameters they use, and test the IDOR on them. Don't stop searching for an hour. 

Also, in any response that retrieves specific data, place the id or anything that identifies something behind the endint. For example, the following request 

GET /api/user

response:

{
"userid":"1233212"
"username":"test",
"public":true",
"github":"flase"
}


try request send :

GET /api/user/{Id_account_2}

Does it retrieve account 2 information using account 1's session, and so on?

Or enter the parameter value in the response as a parameter in the request, for example, for the previous request.

GET /api/user?userId=123321
or
GET /api/user?public=true

and so on 

Any violation of the above instructions will result in your failure to achieve the goal.
```
