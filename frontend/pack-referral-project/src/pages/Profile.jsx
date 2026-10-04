
const Profile = () => {
    
    return (
    
    <div className="flex">
        {/* Create a parent container. */}

        {/* Create smaller blocks inside the parent container. */}

        {/* Child 1: The text container box */}
        <div>
            <h1>Alex Johnson</h1>
            {/* Trying to check if Tailwind is working by checking if this text turns red */}
            <h1 className="text-red-500">Alex Johnson</h1>
            <p>Email: </p>
        </div>
        {/* Child 2: The edit button */}
        <button>Edit Profile</button>
        
    </div> 
    )
}

export default Profile
